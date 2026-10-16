# Building pass: a building around each of the five rooms, with a roof that fades when you walk in

Branch `building-pass` (from `visuals-garage` at `7f5c141`). Status: **all five phases built, new files only** (this file was the Phase 1 proposal; the numbers in sections 2, 4, 6 and 9 are now the real ones). Nothing in an existing file is changed by this branch except the claim rows in `CONTRIBUTING.md`. The edits to existing files are listed in section 8 and need your approval; they are also ready as `docs/building_pass_integration.patch`.

Looks only, like the rest of the plot visuals: nothing is saved, sent through a remote or read back, no gameplay position moves, nothing collides, nothing is bought or opened by touching it.

## 1. Decisions made without asking (change them if you disagree)

| # | Decision | Why |
|---|---|---|
| D-1 | The building is its **own Model** (`PlotBuilding`) next to `PlotRoom` in the player's plot folder, with **its own part budget (64)**. It is not counted in the room's 260. | The rooms already use 256 / 244 / 254 / 253 / 257 of the 260 parts (props included). That leaves **4 / 16 / 6 / 7 / 3** parts, and a roof, four walls, a door and windows cannot be built from 3. See section 4. |
| D-2 | The building sits **outside** the existing shell: its inner face is at 30.2 studs from the plot center, the old walls end at 30.15. No building part touches a room part. | The old shells stay exactly as they are (fingerprints unchanged) and nothing can z-fight with them. |
| D-3 | **Everything of the building fades** (roof, walls, front wall) when you are inside, except a few ground-level pieces (door step, mat, planters). | The camera sits behind the player, often outside the walls. A wall that stays solid would hide the room. After the fade you see the same open room as today. |
| D-4 | The roof is **flat** in every stage (chunky parapet and rooftop props make each stage different). | Blocks only, no `Wedge` (its orientation can't be checked without Studio). A pitched roof is a later change in `PlotBuilding.lua`. |
| D-5 | Fading is decided **per client from the local character's position**. No remote, no server code at runtime, no attribute written by the client. | The server never learns who is inside. Nothing to cheat, nothing to save, no network. |
| D-6 | Integration into `TycoonCore` is **three small edits** that go through the existing `looks()` pcall helper (section 8). A zero-edit alternative exists (section 8, Option B) but is more fragile. | Same pattern as `PlotVisuals`: an art bug can never stop the game. |
| D-7 | Building text is limited to `OFFICE`, `HQ` and `BUILD YOUR STARTUP`. No odds text (D9). | Same rule as the rooms. |

## 2. The shell, stage by stage

Same footprint for all five (62 x 62 outside, a 60.4 x 60.4 inside, 14 studs to the underside of the roof, roof slab 65 x 65 so it overhangs by 1.5). Door opening 9 wide (x -4.5 to 4.5) and 9 high, centered on the walking lane (the lane is only 5 wide, the spawn is in it). Colors come from each room's palette so the outside matches the inside. A "step" is a flat 0.1 stud path on the ground (nothing is solid, so a raised step would only bury the player's feet).

| # | Stage | Walls | Roof and rooftop | Door | Windows | Sign | Ground pieces (stay visible) | Parts built (fade + ground) |
|---|---|---|---|---|---|---|---|---|
| 1 | `Garage` | Rusty dented sheets (3 per side, 3 at the back, 2 + lintel at the front), dark corner posts, ribs on the front | Rust sheet roof with ribs, a blue repair tarp, a stove pipe, an old AC box, a crooked wooden board | Roll-up door pulled up: drum, two hanging slats, guide rails | One small taped window | `BUILD YOUR STARTUP` on the roof board | Concrete path, a tire, a weed tuft, a crate | 51 (47 + 4) |
| 2 | `Seed` | Fresh mint paint, dark teal base band and corner trim | Flat mint roof, teal parapet, a satellite dish, a vent | Four-panel door standing open, teal frame, awning | Two clean windows with sills | `OFFICE` over the door | Path, welcome mat, two small planters | 47 (41 + 6) |
| 3 | `SeriesA` | Red brick with black steel trim, a steel band every few studs | Black steel parapet, skylight boxes, two vents, amber warning stripe | Wide steel frame, one big sliding panel open, two closed roll-up bays beside it | Two glass bays | `OFFICE` on a steel plate | Path, two bollards, two planters | 56 (49 + 7) |
| 4 | `SeriesB` | White panels with a ribbon of cobalt glass, navy columns | Parapet with cobalt cap, glass skylight strip, HVAC units | Glass entrance with a canopy | Four tall glass panels | `OFFICE` on the canopy | Wide path, a bench, two planters | 48 (40 + 8) |
| 5 | `IpoReady` | Polished white with graphite columns, big glass curtain panels | Gold-trimmed parapet, glass dome box, an antenna, a rooftop logo | Lobby with two columns and a deep canopy | Four big curtain-wall panels | `HQ` in a neon-rimmed sign | Wide path, two planters, two flag poles | 55 (46 + 9) |

"Bright chunky cartoon": big simple blocks, thick trim, one accent color per stage, no tiny detail. Built-in Parts and the same material list as the rooms; nothing random, no assets.

## 3. Geometry (all in studs, from the plot's floor-top center, +X right, +Z front)

```
          roof slab  y 14.0 .. 14.9   x, z -32.5 .. 32.5
          walls      y -1.0 .. 14.0   (from the ground, so they rest on it)
   back   z -31.0 .. -30.2            x -30.2 .. 30.2
   sides  x +-31.0 .. +-30.2          z -31.0 .. 31.0
   front  z  30.2 ..  31.0            x -30.2 .. 30.2 with the door x -4.5 .. 4.5, y -1 .. 9
```

- **Tiling, no overlap:** the side walls run the full depth, the back and front walls fit between them. No two building parts overlap in volume except where a trim piece deliberately wraps a wall (it overhangs on the outside only), and no two faces share a plane while overlapping (that flickers, "z-fighting"). `PlotBuildingVisuals.check` tests this.
- **No part inside a room part** (all 5 rooms, all 6 props): proved by `tools/building_test.py`.
- **Reserved zones:** nothing of the building stands in a gameplay zone (`PlotVisuals.zones`). The door opening is 9 wide and the lane 5 wide, the door posts start at x = 4.5.
- The building stays inside 65 studs of the plot center. Plots are 90 apart, so two roofs are at least 25 studs from each other.

## 4. Part budget

The existing limit is 260 parts **per room, props included** (`PlotVisuals.MAX_PARTS`). Today's rooms:

| Stage | Parts now (6 props) | Room left under 260 |
|---|---|---|
| 1 Garage | 256 | 4 |
| 2 Seed | 244 | 16 |
| 3 SeriesA | 254 | 6 |
| 4 SeriesB | 253 | 7 |
| 5 IpoReady | 257 | 3 |

**If the shell had to share the 260, it may use 3 to 16 parts. That is not enough** (a roof, four walls with a door gap and a lintel is 8 parts before any window, trim or sign). So the shell does **not** share it (D-1). The building gets its own budget:

- `PlotBuilding.Budget` = 64 parts per stage (built: 51 / 47 / 56 / 48 / 55), 12 of them ground pieces at most (built: 4 / 6 / 7 / 8 / 9), 0 PointLights, 0 particle emitters, at most 2 SurfaceGuis (built: 1 each).
- The room check (`PlotVisuals.check`) is not run on the building: it measures `PlotRoom` only, and the building is a sibling Model, so the existing 260 limit, the 3-light limit and the room tests are unaffected.
- Total on screen per stage becomes room + building: **307 / 291 / 310 / 301 / 312 parts** (stages 1 to 5). Six plots at the largest stage: 1,872 anchored, non-colliding, shadowless parts for the whole server (six rooms at stage 5 alone are 1,542).

Alternatives I did not take (they need edits to files that are not mine): thin the rooms until the shell fits (edits `PlotArt.lua` and breaks its fingerprints on purpose), or raise 260 (edits `PlotVisuals.lua` and `tools/daily_test.py`, which another session owns).

## 5. How the roof fade works (client only)

Server (new `PlotBuildingVisuals.sync`, called by `TycoonCore` through `looks()`): builds the Model `PlotBuilding` in the plot folder for the current stage and puts the numbers the client needs on it as attributes:

`BoundsMinX/MaxX/MinY/MaxY/MinZ/MaxZ` (world studs, the inside of the building, `MaxY` = underside of the roof), `DoorMinX`, `DoorMaxX`, `DoorDepth` (the apron in front of the door), `Margin`, `FadeSeconds`, `FadeLevels`, `Stage`, `StageKey`. The Model is tagged `PlotBuilding` (CollectionService) and has two children: `Fade` (everything that fades) and `Static` (ground pieces). A stage change replaces the Model (the old one is destroyed).

Client (new `BuildingClient`, a LocalScript, source in `docs/studio_scripts/BuildingClient.lua`):

1. Finds every tagged Model (`GetTagged` + `GetInstanceAddedSignal`, forgets one when it is removed). For each it records the base `Transparency` of every part in `Fade` (glass starts at 0.35, so it must fade from there) and every TextLabel inside a SurfaceGui in it (a SurfaceGui keeps drawing on a part that is fully transparent).
2. Every frame it reads the local character's `HumanoidRootPart` position and runs the pure inside check for each building (a handful of comparisons).
3. The target is 1 (gone) if inside, 0 (solid) if not. The fade value moves toward the target by `dt / FadeSeconds` (0.4 s) and is clamped to 0..1.
4. It writes `Transparency` only when the fade, rounded to one of 20 levels, changes: about 20 writes per part per fade, nothing while settled.
5. At fade 1 a SurfaceGui is disabled; at 0 everything is back to its base values exactly.

**The inside check** (`isInside(bounds, x, y, z, wasInside)`, pure):

- Inside = x and z within the inner faces (edges **inclusive**) and y from 3 studs below the floor top up to the roof underside.
- **Door:** the doorway and a 3.5 stud apron in front of it count as inside (x within the door, z up to `DoorDepth` past the front wall). The front wall starts to fade as you walk up to the door, before you cross it.
- **Corners:** the four inner corners are inside; one stud outside a corner is not.
- **Above the roof:** y above `MaxY` is outside (standing on the roof or flying over it: the roof stays solid).
- **Hysteresis:** once inside, the box is `Margin` (1 stud) bigger, so standing on a wall line doesn't flicker the roof.
- A coordinate that is NaN or infinite is never inside. No character (dead, respawning) holds the last state.

**No gameplay effect:** every building part is anchored with `CanCollide`, `CanTouch` and `CanQuery` all off (nothing can stop a player, a ray, a click or the camera), `CastShadow` off, no PointLights, no `Touched` handler, no remote, nothing saved. The client changes only `Transparency` (and `SurfaceGui.Enabled`) of parts that belong to the building model.

## 6. Performance on phones

- Server: building a stage is one `Model` of at most 64 `Part`s plus two `SurfaceGui`s, built once per stage change (rare) and once on join. `sync` is called every second per player by the income loop: when the stage hasn't changed it does one `FindFirstChild` and one attribute read, no allocation. A building is one `Model` with two child Models, at most 64 `Part`s and one `SurfaceGui`.
- Client: per frame, 6 building checks at most (6 plots) = about 60 comparisons, one `pcall` per building with no closure, no allocation, no raycast, no `GetPartBoundsInBox`. Property writes only while a fade runs (a part per write, about 20 writes per part over 0.4 s, 64 parts at most per building, usually one building at a time).
- Rendering: all parts opaque or glass, no shadows, no lights, no particles, no textures, no meshes. Fading parts are 64 transparent draws for 0.4 s. Once the roof is gone the cost is the same as today (fully transparent parts are not drawn).
- Memory: about 1,900 more tiny anchored parts server-wide. Parts that are far away are not streamed differently from today's.
- Mitigations if a low-end phone struggles: lower `MAX_PARTS`, drop the `Static` pieces, or fade in 10 levels instead of 20 (`FadeLevels`) with no code change.

## 7. Studio steps you do by hand

The repo changes nothing in Studio by itself. After you approve the integration edits (section 8):

1. **ServerScriptService:** create two new ModuleScripts named exactly `PlotBuilding` and `PlotBuildingVisuals`. Paste `PlotBuilding.lua` and `PlotBuildingVisuals.lua` from the repo root. Do this **before** pasting the new `TycoonCore` (it waits for them for 5 seconds inside `pcall`, so it never hangs, but the building would be missing).
2. **StarterPlayer > StarterPlayerScripts:** create a new, empty **LocalScript** named exactly `BuildingClient`. Open `docs/studio_scripts/BuildingClient.lua`, select all, copy, and paste it into that LocalScript. (It is not in the game tree and not at the repo root on purpose.)
3. Paste the changed `TycoonCore` (after approval).
4. View > Drafts: commit every draft. Playtest (section 9 of `docs/STUDIO_SYNC_BUILDING.md`). Publish with Shut down all servers as always.

No new save section, no new remote, no Max Players change: the rollback floor and the publish rules in `docs/PUBLISH_RULES.md` are unchanged.

## 8. The edits to existing files (needs your approval; nothing is applied)

Line numbers are for `visuals-garage` at `7f5c141`. They are ready as `docs/building_pass_integration.patch` (`git apply docs/building_pass_integration.patch` on a branch that has the new files).

**Option A, recommended:**

| # | File | Line | Change |
|---|---|---|---|
| E1 | `TycoonCore.lua` | insert after line 62 (the blank line after the `end` of the "Plot visuals are off" block at 58-61) | 10 lines: require `PlotBuildingVisuals` and `PlotBuilding` inside `pcall` (5 second wait; on failure `warn` and set both to `nil`), same shape as the PlotVisuals block above it. |
| E2 | `TycoonCore.lua` | insert before line 180 (the comment above `syncRoom`, which is 182 to 186), and one line before the `end` at 186 | A new `local function syncBuilding(data)` (7 lines: `if PlotBuildingVisuals and data.looks then looks("building", PlotBuildingVisuals.sync, data.folder, data.looks.center, PlotArt, PlotBuilding, stageOf(data)) end`), and `syncBuilding(data)` as the last line of `syncRoom`. `sync` does nothing when the building already shows that stage. |
| E3 | `TycoonCore.lua` | insert after line 810 (`data.looks = ...newPlot...`) | One line, `syncBuilding(data)`, so the building is there when the player spawns instead of one second later. |

No other line of `TycoonCore.lua` changes (+29 lines, 0 removed). The `data.looks` table is not extended and nothing is saved. **Proved on a scratch copy** (the repo files are untouched): the patch applies cleanly, the patched `TycoonCore.lua` compiles, and `tools/daily_test.py` and `tools/building_test.py` both pass with it, with the same counts as without it.

**Docs to update when the pass is approved** (not done, they are existing files): `README.md` (file list: three new scripts), `docs/PLOT_VISUALS.md` ("Not built yet" paragraph and the open-shell rule: rooms stay open, the building is separate), `CLAUDE.md` (plot visuals bullet: one line on the building and its separate budget), `ROADMAP.md` (the "Full-building pass" line moves to Status), `docs/STUDIO_SYNC.md` (point to `docs/STUDIO_SYNC_BUILDING.md`), and `tools/daily_test.py` (its owner may add the three new scripts to the wiring checks; **not needed for it to keep passing**, proved on a scratch copy, see section 9).

**Option B, zero edits (not built):** a new `BuildingServer` Script in ServerScriptService that watches `workspace` for `*_Startup` folders and their `PlotRoom` `Stage` attribute and builds the building next to it. No `TycoonCore` change, but it guesses the plot center from the `Floor` Part, depends on the folder naming and runs a second watcher. I recommend A; B is a day of work if you prefer it.

## 9. What was checked, and what cannot be

**Checked** (`python3 tools/building_test.py`, with the free `luau` binary; `tools/daily_test.py` is not touched and still passes):

- **398 checks and 57 mutation runs** in `tools/building_test.py`: the data (`validate`), the five buildings built in a fake Roblox with real vector and rotation maths (parts 51 / 47 / 56 / 48 / 55, flags, no light, no emitter, text whitelist, doorway clear, no part in a gameplay zone or in a room part, nothing floating, no two faces on one plane), `sync`, the pure inside check (door, corners, y above the roof, hysteresis, NaN and infinity), the pure fade maths (always 0 to 1, never overshoots, bad frame times), the real `BuildingClient` script running against a fake world (walk in, walk out, reversing mid-fade, door apron, hysteresis, a stage change while inside, no character, two buildings, late parts, bad attributes, 3,000 random frames), the fingerprints of the five rooms, the props and the layout (equal to the ones `daily_test.py` pins, and the same layout read from the scripts), and source checks (the client never touches a remote, collision or position; the two copies of the maths are the same text; no existing file is edited).
- **Mutation runs:** 12 breaks of the inside check and 11 of the fade, each run on the module and on the client copy, plus 11 breaks of the client's wiring: **57 of 57 caught**.
- **The integration patch** applies to the base `TycoonCore.lua`, compiles, and with it applied both test files pass with the same counts (`python3 tools/building_test.py --integration`).

**Cannot be checked without Studio, and is not checked:** how any of it looks (colors, proportions, whether the front wall, roof and sign read well from the default camera), the real fade speed on a phone, Roblox's own camera behavior near the walls and roof, `Glass` and `Neon` rendering, that `NormalId.Back` is the +Z face (the code follows `PlotVisuals`), that the `Cylinder` parts stand the way they are rotated, whether a `LocalScript` pasted by hand finds the tag in time, StreamingEnabled behavior, and frame rate on a real phone. The list to look at is in `docs/STUDIO_SYNC_BUILDING.md` section (c); the judgment calls and risks are in `docs/BUILDING_PASS_NOTES.md`.
