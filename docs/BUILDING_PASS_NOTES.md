# Building pass: notes, judgment calls and what was not tested

> **Built differently in lobby L2 (2026-10-16, branch `lobby-all`).** This pass's maths, inside check and fade client were kept (BuildingClient is now at the repo root and works in each garage's turned frame). Its Parts-only, never-solid shell was replaced by the five kit buildings with invisible solid walls (docs/PLOT_VISUALS.md, "The building"; docs/LOBBY_ALL_PROGRESS.md). The integration patch is not applied: L2 wired TycoonCore by hand (two of its three edits). The Studio steps are in docs/STUDIO_SYNC_LOBBY.md, not in docs/STUDIO_SYNC_BUILDING.md.

Branch `building-pass`. **No phase was blocked.** This file is where I record what you should know that is not in the proposal.

## Judgment calls (change any of them)

1. **Own part budget for the building (64), not the room's 260.** You asked to stay under the existing 260 limit and to say how many parts the shell may use. The rooms already use 256 / 244 / 254 / 253 / 257, which leaves 4 / 16 / 6 / 7 / 3 parts: **not enough for any shell**. The building is therefore a separate Model with its own budget, and the room's own check and limit are untouched. Staying inside the single 260 would need `PlotArt.lua` thinned (not allowed here) or `PlotVisuals.MAX_PARTS` raised (a file with fingerprints and tests owned elsewhere). Total on screen: 307 / 291 / 310 / 301 / 312 per stage.
2. **The building stands outside the old shells** (inner face 30.2, the old walls end at 30.15). So the building never overlaps or z-fights with a room part, and the rooms stay exactly as they are. The cost: the plot looks 62 x 62 from outside, with a 65 x 65 roof.
3. **Everything fades, not only the roof**: roof, walls and front. Otherwise the camera, which sits behind the player and often outside a wall, looks at a wall.
4. **Flat roofs only, no `Wedge`.** Its orientation can't be checked without Studio.
5. **No elevated step at the door**, only flat ground paths: nothing is solid, so a raised step would bury the character's feet.
6. **Everything is CastShadow off.** This avoids both a dark room under a closed roof when seen from outside, and shadow cost on phones. If you want the roof to shade the room, that is a one-word change in `PlotBuildingVisuals.buildPart`, and the checker (`part.CastShadow`) must change with it.
7. **`PlotBuildingVisuals` duplicates ~40 lines of `PlotVisuals.buildPart`** instead of requiring `PlotVisuals`, so a failing module can never take the other one down, and the flags (never solid, never touched, never queried, no shadow) are enforced in one place that cannot be loosened by the art data.
8. **The inside check and fade maths exist twice** (in `PlotBuildingVisuals.lua` and, pasted, in `BuildingClient.lua`) because a LocalScript can't require something from ServerScriptService. The two copies sit between `BUILDINGMATH-START` and `BUILDINGMATH-END` and the tests fail if they differ and run the same unit tests on both.
9. **The integration is a patch, not an edit.** `docs/building_pass_integration.patch` (+29 lines in `TycoonCore.lua`, nothing removed) is not applied. `tools/daily_test.py` was not touched and passes with and without it. A zero-edit alternative (a watcher Script) is described in the proposal and not built.
10. **`tools/building_test.py --integration`** is an optional flag (it copies the repo to a temp folder and runs both suites with the patch applied); the default run does not need git except for the "no existing file is edited" check, which skips itself when the base commit `7f5c141` is not available.

## Risks I could not rule out

- **Looks.** I rendered the part boxes to flat pictures to catch layout mistakes (door gap, windows, roof props) but never saw Roblox draw them. Expect to change colors and proportions.
- **Text direction.** Signs use `Face = Back` for the +Z side because `PlotVisuals` does. If the letters are on the wrong side or mirrored, change `text.face` for the signs in `PlotBuilding.lua` (`doorSign` and the garage roof board).
- **Cylinders** (door drum, vents, planters, bollards, helipad) use `rot = { 0, 0, 90 }` to stand up, as `PlotArt` does for its own uprights.
- **Glass.** `Glass` parts with `Transparency` 0.2 to 0.35 fade from that value. If `Glass` renders oddly on phones, change the material to `SmoothPlastic` in the data.
- **Streaming.** If StreamingEnabled is ever turned on, parts that stream in late take the current fade (tested in the fake), but a building far away may be partly missing as in any other model.
- **`BuildingClient` runs after the character exists.** Until a character exists the roof stays closed; it opens within 0.4 s of the first frame the character is inside.
- **The preview snippet** in `docs/STUDIO_SYNC_BUILDING.md` was not run in Studio; its calls are the same ones the tests run in the fake.

## How to re-run everything

```
LUAU=/path/to/luau python3 tools/daily_test.py
LUAU=/path/to/luau python3 tools/building_test.py            # add --integration to try the patch on a temp copy
```
