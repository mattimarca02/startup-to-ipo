# Model slots: ready-made 3D models for the five buildings, with a Parts fallback

> **Superseded (2026-10-16).** The kit plan (docs/KIT_MODELS.md, `ReplicatedStorage.KitModels`) replaced this design on branch `lobby-all`: see docs/LOBBY_ALL_PROGRESS.md and docs/PLOT_VISUALS.md, "The building". Kept for its measurements and reasoning.

Plan (2026-10-16, branch `lobby-all`), then built on the same branch (`ModelSlots.lua`, the slot data in `PlotBuilding.lua`, the tests in `tools/building_test.py`). It changes docs/BUILDING_STAGES_PROPOSAL.md in one way: every wall, door, window, floor piece and piece of furniture of the five buildings is a **slot**. A slot is built from a ready-made model when the owner has added one, and from its **Parts version** otherwise. **No model is needed for the game or for any test.** No asset ID appears anywhere in the code or the data; this branch downloads, generates and inserts nothing.

## 1. The kit

### 1.1 Rules every piece follows

- **The 4-stud grid.** Width and height of every piece are multiples of 4 studs (depth too for furniture). Exceptions, because the building's walls stand in a 2-stud band between the room and the plot's edge: wall-type pieces are **1 deep**, corner posts **2 x 2**, flat pieces (mats, paths, rugs) are 0.2 high.
- **The slot box.** Each placement of a slot has a box: width (x), height (y), depth (z) in the slot's own frame. Its **front is its +Z side**: the outside of a wall, the side of a desk where the person sits, the face of a sign. Its bottom is the floor or the ground.
- **How a model fits.** `fit = "uniform"` (default): scaled by one factor until it fills the box on the tightest side; refused if it then fills less than 80% of the box's width or height. `fit = "stretch"` (floors, roofs, paths, parapets, long strips only): scaled on each axis to the box exactly; refused if any part of it is turned other than by quarter turns.
- **Solid pieces never get solid models.** A model's parts are never `CanCollide`. A solid slot (outer walls, corner posts, windows, lintels, roof, floor strips) keeps its **collider**: the solid pieces of its Parts version, made invisible. So the walls are closed and the lane is clear whatever model is used.

### 1.2 Triangle budgets

A built-in block Part costs 12 triangles, so the Parts versions (80 to 210 parts per building) cost about 1,000 to 4,000 triangles; the rooms (up to 260 parts) about 3,000. Models are richer. The budget below allows about 10 times the Parts version's detail, counted for **every placement** (a wall panel used 30 times counts 30 times):

| Piece kind | Triangles per piece (cap) | Why |
|---|---|---|
| Wall panel, narrow panel, corner post, upper panel | 200 | used 20 to 60 times per building: a flat panel with some relief |
| Window panel, upper window | 300 | frame and glass |
| Lintel, sign board, parapet strip | 300 | |
| Roof, floor strip, path | 600 / 100 / 100 | big flat pieces |
| Door piece (roll-up drum, door leaf, canopy, awning) | 1,000 | the eye-catcher of the front |
| Roof prop (vent, dish, HVAC, skylight, antenna, stove pipe, tarp, board) | 600 | |
| Small furniture (chair, beanbag, drum, printer, cooler, planter) | 500 | |
| Big furniture (desk, counter, sofa, shelf, lockers, meeting table) | 1,200 | |
| Plant, flag pole | 800 | |

| Building | Triangle budget | Parts budget (colliders included) |
|---|---|---|
| 1 Garage | 10,000 | 80 |
| 2 Small Office | 15,000 | 110 |
| 3 Big Office | 20,000 | 140 |
| 4 Small Corporate | 30,000 | 180 |
| 5 Big Corporate | 40,000 | 210 |

**Phone-safe, and why these numbers:** with StreamingEnabled on, a phone keeps about two or three garages near the player (minimum radius 64 studs, **unverified**). Three buildings 5 at the full budget are 120,000 triangles; with three rooms (about 9,000), six characters and the plaza, a phone draws well under 150,000 triangles for buildings and rooms. The part budget stays the real cap on instance count (each model part counts as a part, like the Parts it replaces, colliders included), so a model never raises the 470 parts per garage of BUILDING_STAGES_PROPOSAL.md section 3. All numbers are **placeholders until the Studio phone test** (docs/STUDIO_SYNC_LOBBY.md): if a low-end phone drops under 30 fps, lower the budgets in `PlotBuilding` (data only).

**How the code counts triangles:** a script cannot read a mesh's triangle count **(unverified: no such property is known to me)**. So each model carries an attribute **`Triangles`**, the number Studio shows when the mesh is imported or selected. A model without it, or above its piece cap, is refused; a placement that would take the building over its budget uses its Parts version instead (in data order, so it is always the same pieces).

### 1.3 The shell kit (every building has its own copy of these slots)

`H` = the ground-floor wall height: 16 for the Garage, 20 for the others. Counts are placements per building, Garage / Small Office / Big Office / Small Corporate / Big Corporate (`-` = not used).

| Slot | Box (W x H x D) | Fit | Solid | Placements | What it is |
|---|---|---|---|---|---|
| `WallPanel` | 8 x H x 1 | uniform | yes | 22 / 21 / 22 / 21 / 17 | a plain wall panel |
| `WallPanelNarrow` | 4 x H x 1 | uniform | yes | 0 / 4 / 2 / 4 / 2 | the 4-wide end of a run |
| `WallWindow` | 8 x H x 1 | uniform | yes | 2 / 6 / 8 / 12 / 16 | a wall panel with a window |
| `Corner` | 2 x H x 2 | uniform | yes | 4 each | corner post |
| `Lintel` | door width x (H - 12) x 1 | stretch | yes | 1 each (16 x 4, 12 x 8, 16 x 8, 20 x 8, 20 x 8) | the wall over the door |
| `UpperPanel` | 8 x 16 x 1 | uniform | yes | - / - / - / 18 / 36 | a wall panel of an upper storey |
| `UpperWindow` | 8 x 16 x 1 | uniform | yes | - / - / - / 18 / 36 | an upper-storey window |
| `Roof` | W x 1 x D | stretch | yes | 1 each | the roof slab |
| `FloorStrip` | strip x 1 x strip | stretch | yes | - / 4 / 4 / 4 / 4 | the floor added around the room |
| `Parapet` | strip x 4 x 1 | stretch | no | - / 4 / 4 / 4 / 4 | the low wall around a flat roof |
| `DoorPiece` | per building (Garage 16 x 4 x 2 drum) | uniform | no | 1 to 3 | roll-up drum, open door leaf, awning, canopy |
| `SignBoard` | 12 x 4 x 1 (Garage 16 x 4 x 1) | uniform | no | 1 each | the board over the door (the code writes the text on its own plate) |
| `RoofBoard` | 20 x 8 x 1 | uniform | no | 1 / - / - / - / - | the crooked BUILD YOUR STARTUP board |
| `RoofProp` | 4 x 4 x 4 (antenna 4 x 16 x 4) | uniform | no | 2 to 6 | vents, dish, HVAC, skylights, stove pipe, antenna |
| `Tower` | 32 x 12 x 24 | uniform | yes | - / - / - / - / 1 | the HQ tower over the middle |

### 1.4 Furniture and outside pieces per building

| Building | Slot (box W x H x D) |
|---|---|
| Garage | `OilDrum` (4 x 4 x 4), `TireStack` (4 x 4 x 4), `Shelf` (8 x 8 x 4), outside `Path` (stretch, flat), `Tire` (4 x 4 x 4) |
| Small Office | `BikeRack` (8 x 4 x 4), `CoatRack` (4 x 8 x 4), `WaterCooler` (4 x 8 x 4), `Plant` (4 x 8 x 4), `Lockers` (8 x 8 x 4), `Bookshelf` (8 x 8 x 4), outside `Path`, `Mat` (8 x 0.2 x 4), `Planter` (4 x 4 x 4) |
| Big Office | `Beanbag` (4 x 4 x 4), `LowTable` (8 x 4 x 4), `Rug` (8 x 0.2 x 8), `Counter` (16 x 4 x 4), `Fridge` (4 x 8 x 4), `CoffeeBar` (8 x 4 x 4), `Shelf` (8 x 8 x 4), `Printer` (4 x 4 x 4), outside `Path`, `Bollard` (4 x 4 x 4), `Planter` |
| Small Corporate | `ReceptionDesk` (12 x 4 x 4), `LogoPanel` (8 x 8 x 1), `WaitingChair` (4 x 4 x 4), `GlassWall` (8 x 8 x 1), `MeetingTable` (12 x 4 x 4), `Chair` (4 x 4 x 4), `WallScreen` (8 x 4 x 1), `OfficeDesk` (8 x 4 x 4), `Printer`, `Plant`, outside `Path`, `Bench` (8 x 4 x 4), `Planter` |
| Big Corporate | `ReceptionDesk` (16 x 4 x 4), `LogoWall` (12 x 12 x 1), `GlassWall`, `MeetingTable`, `Chair`, `WallScreen`, `Sofa` (12 x 4 x 4), `Armchair` (4 x 4 x 4), `Plant` (4 x 12 x 4), `OfficeDesk`, outside `Path`, `FlagPole` (4 x 20 x 4), `Planter` |

The exact list (every placement, its box and its Parts version) is `PlotBuilding.lua`; `tools/building_test.py` checks that every slot named here exists there and every box is on the grid.

### 1.5 The owner's shopping list

What to find or make for each slot, in plain words. **Creator Store** = Studio's Toolbox > Creator Store > Models (search terms in quotes). **Cube** = Roblox's text-to-3D generation (Roblox Cube) **(unverified: where it is offered in your Studio)**; the prompts are written to give a flat-shaded, low-detail piece that fits the box. Add only what you like; every empty slot keeps its Parts version.

| Building and slot | Find or make | Creator Store search | Cube prompt |
|---|---|---|---|
| Garage `WallPanel` | a rusty corrugated metal sheet, upright, flat back | "corrugated metal wall low poly", "rusty sheet metal panel" | "low-poly cartoon rusty corrugated metal wall panel, flat, tall rectangle 1 by 2, chunky ridges, no text" |
| Garage `WallWindow` | the same sheet with a small dusty window and tape | "rusty shed window low poly" | "low-poly cartoon rusty metal wall panel with a small dirty window crossed by tape, flat, no text" |
| Garage `Corner` | a dark square post | "metal post low poly" | "low-poly dark steel square post, tall, plain" |
| Garage `DoorPiece` | a pulled-up roll-up garage door drum | "roll up garage door low poly" | "low-poly cartoon rolled-up garage door drum, horizontal cylinder with side brackets, grey metal" |
| Garage `Roof`, `RoofProp`, `RoofBoard` | flat tin roof, stove pipe, AC box, blank wooden board | "tin roof low poly", "stove pipe chimney", "old air conditioner low poly", "wooden sign board blank" | "low-poly flat tin roof slab with ribs", "low-poly cartoon stove pipe chimney", "low-poly blank wooden sign board, no text" |
| Garage `OilDrum`, `TireStack`, `Shelf`, `Tire` | oil drum, stack of tires, metal shelf with paint cans, one tire | "oil drum low poly", "tire stack", "garage shelf" | "low-poly cartoon red oil drum", "low-poly stack of three black tires", "low-poly metal shelf with paint cans, no labels" |
| Small Office `WallPanel`, `WallWindow` | painted panel (mint is set by the Parts version; a model brings its own color), panel with a white-framed window | "office wall panel low poly", "office window wall" | "low-poly cartoon painted wall panel, mint green, dark teal base band", "low-poly cartoon mint wall panel with a white framed window" |
| Small Office `DoorPiece`, `SignBoard` | glass double door standing open, coral awning, blank board | "glass door open low poly", "shop awning low poly" | "low-poly cartoon striped coral awning", "low-poly blank dark sign board, no text" |
| Small Office furniture | bike rack, coat rack, water cooler, potted plant, lockers, bookshelf, planter, doormat | the item's name plus "low poly" | "low-poly cartoon <item>, chunky, bright colors, no text or logo" |
| Big Office `WallPanel`, `WallWindow` | red brick panel with a black steel band, steel-framed glass bay | "brick wall panel low poly", "industrial window low poly" | "low-poly cartoon red brick wall panel with a black steel band", "low-poly black steel framed glass window panel" |
| Big Office `DoorPiece`, `RoofProp` | sliding steel door (open), skylight box, roof vent | "sliding barn door metal", "skylight low poly", "roof vent" | "low-poly cartoon open sliding steel door", "low-poly glass skylight box" |
| Big Office furniture | beanbag, low table, rug, kitchen counter, fridge, coffee bar, shelf, printer, bollard | the item's name plus "low poly" | as above |
| Small Corporate `WallPanel`, `WallWindow`, `UpperPanel`, `UpperWindow` | white office panel with a navy column, cobalt glass ribbon window | "modern office facade panel", "glass curtain wall low poly" | "low-poly cartoon white office facade panel with navy column", "low-poly cobalt blue glass window panel, white frame" |
| Small Corporate `DoorPiece` | glass entrance canopy | "entrance canopy low poly" | "low-poly cartoon navy entrance canopy" |
| Small Corporate furniture | reception desk, blank logo panel, waiting chair, glass partition, meeting table, office chair, wall screen (blank), office desk with monitor, printer, plant, bench | "reception desk low poly", "meeting table", "office desk low poly" | "low-poly cartoon <item>, white and navy, no text" |
| Big Corporate shell and `Tower` | polished white curtain wall, graphite column, gold trim, a glass tower block | "glass skyscraper low poly", "modern HQ facade" | "low-poly cartoon glass office tower block, white and graphite, gold trim, flat roof" |
| Big Corporate furniture | big reception desk, blank logo wall, sofa, armchair, tall plant, flag pole (blank flag) | "lobby sofa low poly", "flag pole" | "low-poly cartoon <item>, white, graphite and gold, no text" |

Never pick a model with a brand, a logo, a word, a face or a real company's look.

## 2. Names and the folder

```
ReplicatedStorage
  BuildingModels            (Folder)
    Garage                  (Folder: the building's key, exactly)
      WallPanel             (Model: the slot's name, exactly)
      OilDrum               (Model)
    SmallOffice
    BigOffice
    SmallCorporate
    BigCorporate
```

- The building folders are named by `PlotBuilding.Buildings[i].key`: `Garage`, `SmallOffice`, `BigOffice`, `SmallCorporate`, `BigCorporate`. The slot names are the ones in section 1, exactly (case counts).
- One template per slot per building. A slot shared by two buildings (`Plant`, `Printer`) needs a copy in each folder: each building can look different.
- Each template is a **Model** with two attributes the owner sets: **`Triangles`** (number) and **`Checked`** (true, set after section 4's checklist). Optional: `Credit` (text, who made it and where it came from) for the owner's own records.
- The **pivot** of the template decides which way it faces: its front (Studio's Front face, the pivot's LookVector) becomes the slot's front (+Z of the slot, the outside of a wall).
- `ReplicatedStorage` copies every template to every phone (memory). If that matters later, the folder can move to `ServerStorage` by changing one line (`ModelSlots.FOLDER_SERVICE`): only the server builds. Owner question 1.

## 3. How the code uses a template (`ModelSlots.lua`)

For each placement of a slot, the builder asks `ModelSlots.fit(template, slot)`. It answers with a ready model or with the reason it refused; on any refusal the Parts version is built.

1. **Find it:** `BuildingModels.<Building>.<Slot>`. Missing folder or template: Parts version, reason `"no model"`.
2. **Check the template** before copying: it is a Model; `Checked == true`; `Triangles` is a whole number, at least 1, at most the piece cap (1.2); at most `ModelSlots.MAX_PARTS_PER_PIECE` (12) BaseParts; at least one BasePart. Otherwise: refused.
3. **Clone** (never the template itself) and **clean the copy**: every descendant whose class is not on the allow-list is **deleted** before the copy goes anywhere: Scripts, LocalScripts and ModuleScripts first, then sounds, lights, particle emitters, fire, smoke, prompts, click detectors, GUIs (they can hold text), humanoids, values, welds and constraints (everything is anchored) and anything unknown. **Allow-list:** `Model`, `Folder`, `Part`, `MeshPart`, `WedgePart`, `CornerWedgePart`, `UnionOperation`, `SpecialMesh`, `SurfaceAppearance`, `Texture`, `Decal`. The names of deleted instances are kept for the Debug report.
4. **Every part:** `Anchored` on, `CanCollide` off, `CanTouch` off, `CanQuery` off, `CastShadow` off when its longest side is under 2 studs. (Solid slots keep their collider from the Parts version, section 1.1.)
5. **Scale** to the slot box (`uniform` or `stretch`, section 1.1) and **place** its bounding box's bottom-center on the slot's bottom-center, its front to the slot's front. A scale outside 0.25 to 4, a model that would not fill 80% of the box, or a non-quarter-turned part in a stretch slot: refused.
6. **Budget:** the building's running triangle sum plus this piece's `Triangles` must stay under the building's budget, and the building's parts (colliders included) under its part budget. Otherwise this placement uses its Parts version (reason `"over the building's budget"`).
7. **Mark it:** the slot's Model gets attributes `Slot`, `Source` (`"model"` or `"parts"`) and `Why` (the refusal reason). The Studio Debug button "Building model slots" lists them for your garage.

A template is only ever read, never changed, moved or deleted by the code. Building the Parts version never needs a template.

**Templates are checked once more at server start:** a Script inside `BuildingModels` could run on its own if it is a `Script` with `RunContext = Client` **(unverified for templates in ReplicatedStorage)**; the server deletes every script it finds under `BuildingModels` at start (with a warning naming it), and the template it came from is refused until the owner re-adds a clean one (its `Checked` is cleared). The real protection is section 4: never put a model with a script into the place.

## 4. Before adding a model: licence and safety checklist

For **each** model, before it goes into `BuildingModels`:

1. **Free to use in your experience.** On the Creator Store page: it is offered free, by a creator you trust (verified badge or a known studio), and nothing on the page says "not for use in games" or asks for credit you cannot give. A Cube-generated model is yours to use **(unverified: re-read Roblox's terms for generated content the day you add one)**.
2. **No scripts.** The Toolbox shows a warning when a model contains scripts. In Explorer, expand every child: no `Script`, `LocalScript` or `ModuleScript`. If one is there, **do not use the model** (delete it, pick another).
3. **No sounds, lights, particles, fire, smoke** (delete them, or pick another).
4. **No text:** no decal or texture with words, logos, brands, faces or signatures; no SurfaceGui or BillboardGui. Text stays OFFICE, HQ, BUILD YOUR STARTUP and the garage sign (the code's own).
5. **No odds words** anywhere in the model's names (D9).
6. **Triangles:** select the model's MeshParts and read the triangle count Studio shows (the import window, or the Properties of each MeshPart) **(unverified where)**; add them up; at most the piece cap of section 1.2.
7. **Parts:** at most 12 BaseParts.
8. **Size and facing:** put it next to the Parts version in a playtest and compare; set the pivot so the front is the side people see.

**Adding one model in Studio (one at a time):**

1. Toolbox > Creator Store > Models, search (section 1.5); or make it with Cube. Insert it into **Workspace**.
2. Go through the checklist above in Explorer. Delete what must go.
3. Select all its pieces, **Group** (Cmd/Ctrl+G) into one Model, rename the Model to the slot's exact name (for example `WallPanel`).
4. Set its pivot (Model tab > Pivot > Edit Pivot) so the blue Front arrow points to the side people see.
5. In Properties > Attributes, add `Triangles` (Number) with the count from step 6 of the checklist, and `Checked` (Boolean) = true.
6. Drag it into `ReplicatedStorage > BuildingModels > <Building>` (create the folders the first time, named exactly as in section 2).
7. Playtest (F5). Shop > Debug > "Building model slots": your slot says `model`. If it says `parts`, the reason is next to it (fix and try again). Walk through the building: the walls are still solid, the door still open.
8. View > Drafts: nothing to commit (models are not scripts). The place keeps the model; note what you added in the table below.
9. Publish later with the rest, as always (docs/PUBLISH_RULES.md).

| Building | Slot | Where it came from (creator, Creator Store page or "Cube") | Triangles | Added on |
|---|---|---|---|---|
| | | | | |

**Studio MCP (later, optional):** the Roblox Studio MCP can search the Creator Store and insert candidates into a staging folder (`Workspace.MODEL_CANDIDATES`) for the owner to review; it is not used on this branch. That is a step for a later Studio session, with the owner choosing every model and doing the checklist by hand.

## 5. What the "no assets" rule becomes (owner to approve; CLAUDE.md is not edited on this branch)

Today: CLAUDE.md:33 ("built-in Parts and the allowed materials only, no assets") and docs/PLOT_VISUALS.md:7 and :38. Proposed wording, replacing those phrases:

> **Rooms (`PlotArt`) use built-in Parts and the allowed materials only, no assets.** **Buildings (`PlotBuilding`)** are built from Parts by default; any building piece may instead be a ready-made model the owner has checked (docs/MODEL_ASSETS_PLAN.md: free to use, no scripts, sounds, lights or text, `Triangles` and `Checked` set), kept in the place under `ReplicatedStorage.BuildingModels.<Building>.<Slot>` and placed only by `ModelSlots`, which cleans, caps and scales it, never makes it solid, and builds the Parts version instead when anything is off or missing. No asset ID is ever written in code or data; no test may need a model.

## 6. Owner questions

1. Keep the templates in `ReplicatedStorage` (as asked; every phone downloads them) or move them to `ServerStorage` (only the server needs them)?
2. The triangle budgets are placeholders: run the phone test (docs/STUDIO_SYNC_LOBBY.md) with the first real models and adjust.
3. Require `Checked = true` on every model (recommended), or trust the folder?
