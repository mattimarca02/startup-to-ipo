# lobby-all: progress (the running task list)

Branch `lobby-all`, from `main` `f6a546f` (the latest `origin/main` on 2026-10-16), worktree `../lobby-all`. It builds what is left of docs/LOBBY_GARAGE_PROPOSAL.md (stages L2, L3, L4, L5, in that order) plus the five buildings made from the 3D kit (docs/KIT_MODELS.md). It ends with a pull request into `main` that is **not merged** by this work. A new session resumes from this file: take the first stage that is not "done".

| Stage | What | State |
|---|---|---|
| setup | `origin/kit-models` merged first, then `origin/building-pass` (CONTRIBUTING conflict: both sides' rows kept); claim rows for every file this branch edits | done |
| L2 | permanent closed building: `buildGarages`, the Floor in the garage, the garage sign, reset on leave; the five kit buildings (PlotBuilding, PlotBuildingVisuals), `BuildingClient` at the root, `tools/building_test.py` | next |
| L3 | the claim behind `LobbyConfig.ClaimEnabled` (ships false): `claimGarage` with the moved CLAIMLOAD block, states, prompts, `UserId` hold, Free room, receipts, `LobbyClient`, `tools/lobby_test.py` | to do |
| L4 | the ring and the plaza (`LobbyConfig.Garages`, WorldVisuals ring layout), persistent shells | to do |
| L5 | docs (CLAUDE.md, ROADMAP.md, README, PUBLISH_RULES), docs/STUDIO_SYNC_LOBBY.md (the one Studio list), claims released, pull request | to do |

## Before this session (what was there, and what happened to it)

- An earlier session made the branch with two commits on top of `main` (tag `lobby-B0`): docs/BUILDING_STAGES_PROPOSAL.md, docs/MODEL_ASSETS_PLAN.md and docs/previews/buildings_plan.svg. They plan a "model slot" design (`ReplicatedStorage.BuildingModels`, Parts only, nothing solid). **The kit plan replaces it** (KitModels, solid invisible boxes, growing footprints). Those two docs stay in the repo marked superseded; their measured facts (stage 1 weeds and dirt, the stage 5 skyline) are re-measured by tools/building_test.py with the real PlotArt.
- That session also left four uncommitted files (ModelSlots.lua, PlotBuilding.lua, PlotBuildingVisuals.lua, tools/building_test.py of the slot design). They were moved, not deleted, to `../lobby-all-b1-wip-backup/`. Its fake Roblox (classes, MeshPart, Clone) was reused in tools/building_test.py; its slot code was not (it is for `BuildingModels`).
- The local branch `lobby-all-v1` (worktree `../lobby-all-v1`) is the same commit as `lobby-B0`, with no other work.

## Baseline (before any change, Luau 0.742)

daily_test 2,746 checks, 281 mutants; hud_test 1,072 / 94; world_test 350 / 82; icon_test 371 / 68; shop_ux_test 6,300 / 101; lobby_test 27 / 26. building-pass's own building_test stops at its first source pin (L1 moved the landing into `plotFrame`), as the proposal's section 3.1 expected.
`git apply --check docs/building_pass_integration.patch` on `main`'s TycoonCore: **applies** (exit 0). L2 takes two of its three edits (the require and the `syncRoom` hook); the third (after the room line, inside CLAIMLOAD) is dropped, as section 2.2 says.

## Design decisions (where the plan was silent)

1. **The garage frame** is the building's frame: origin at the middle of the Floor's top, +X right, +Z the front (the plaza), y -1 the ground. Every building number below is in it, and all of it turns with `plotFrame`.
2. **Front fixed:** every stage's front wall is z 30.2 to 32.2 (the kit's walls are 2 deep; the room's parts end at 30.15; the lot ends at 32.3).
3. **Footprints** (x half-width, back face): Garage 34, -34 (68 x 66.2); Small Office 36.2, -36.2 (72.4 x 68.4); Big Office 38, -38 (76 x 70.2); Small Corporate 40, -40 (80 x 72.2); Big Corporate 41.2, -42.2 (82.4 x 74.4). All inside the lot (82.6 x 86.6), all larger than building-pass's 62 x 62. Big Corporate's back stops at -42.2 so the stage 5 room's skyline (z -43 to -49) stays outside, behind it.
4. **Solid = 7 invisible boxes per stage** (left, right, back, front left, front right, lintel, roof). Kit MeshParts and fallback Parts never collide. The roof box is over the floor but starts at y 12 (a jumping player's head stays under it); every other box is outside the 60 x 60.
5. **Doorway:** solid gap 20 wide x 11 high (Garage: the WallGarage hole), 9 x 9 (offices: WallDoor), 10 x 11 (Small Corporate: the revolving door), 12 x 10 (Big Corporate). Always at least 9 x 9.
6. **The furniture stays visible when the shell fades** (it is in the `Static` group): the fade is for the shell, so the player sees the interior. Every solid box is Transparency 1, every shell part reaches 1 at full fade. (The prompt's "every part at least 0.25 transparent" is read as every shell and solid part; furniture is non-solid and never pulls the camera.)
7. **Pieces in front of the facade** (plants, door leaf, columns, pillars, the bulb) stay before z 38 (WorldArt's `plotReach.front` is 40) and out of the lane, the apron and the claim post's spot (x 6 to 10, z 34.2 to 36.2: L3's post 3 studs outside the front wall at x +7, and its lamp).
8. **Upper stories** are exterior only: a hollow shell over a ceiling slab. Big Corporate is a one-story podium on the whole footprint with a 5-story tower (48 x 32) on top, so it fits the 160-part budget.

## Problems found in the plan (with the fix used, each one data only)

- **P1. WallDoor's opening is 6 wide; the doorway must be at least 9.** The kit may not be stretched. Fix: the solid doorway stays 9 wide (boxes at x +-4.5); the WallDoor mesh's jambs stand 1.5 studs into it on each side, non-solid (a player walking off-center goes through 1.5 studs of door frame). Alternative if the owner prefers: no WallDoor, a plain 9-wide opening with a RoofEdge lintel (one line per stage in PlotBuilding).
- **P2. Big Corporate's BoardTable (8 deep), Rug (8 deep) and Bell (6 deep) cannot stand in a band 4 deep.** Fix: Big Corporate's back band is 8 deep (z -40.2 to -32.2, still outside the room and every zone); its side bands stay 4. Alternative: leave those three out (one line).
- **P3. Small Corporate's "two short pillars":** the kit has no short pillar and pieces may not be scaled. Fix: two `Corner` pieces (2 x 2 x 14) beside the revolving door.

## How to continue

```
cd ../lobby-all && git pull --ff-only
LUAU=~/.local/luau-dl/luau python3 tools/building_test.py    # and daily, hud, world, icon, shop_ux, lobby
```
Then take the first stage marked "next" above, commit, push (`git push origin lobby-all`, never `--force`), and update this file.
