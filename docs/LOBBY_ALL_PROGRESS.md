# lobby-all-v1: progress (stopped by the owner, 2026-10-16)

Branch `lobby-all-v1`, from `main` `f6a546f`. Work stopped on the owner's request. **Nothing is merged and there is no pull request.**
`origin/lobby-all` already has commit `8ce4ffd` and tag `lobby-B0` from this session (pushed before the owner said another session owns that branch). This branch starts from that same commit.

## Stages

| Stage | State | What exists |
|---|---|---|
| B0: design docs | **done** (tag `lobby-B0`, on `lobby-all` too) | docs/BUILDING_STAGES_PROPOSAL.md, docs/MODEL_ASSETS_PLAN.md, docs/previews/buildings_plan.svg (a sketch from the proposal's numbers) |
| B1: model slots, building data and builder (new files, not wired) | **half done, untested** | `ModelSlots.lua` (template allow-list, script stripping, caps, scaling, refusal reasons), `PlotBuilding.lua` (slot catalog and building 1, the Garage), `PlotBuildingVisuals.lua` (build, sync, sign, slot report, unstick maths, the fade maths, validate, check). **None of it has ever run.** Known open fixes from review: the Garage's door drum (2.4 across) sticks out of its 2-deep box; the slot catalog lists slots no building uses yet (WallPanelNarrow, UpperPanel, UpperWindow, FloorStrip, Parapet). |
| B1: `tools/building_test.py` | **lost, must be rewritten** | It was written but never run, and it was deleted from the `lobby-all` worktree before it was committed (something else cleaned that worktree). It is not on this branch. |
| L2 (permanent closed building), L3 (claim behind `LobbyConfig.ClaimEnabled`), L4 (ring and plaza), L5 (docs, Studio list) | **not started** | |
| B2-B5 (Small Office, Big Office, Small Corporate, Big Corporate) | **not started** (designed in the B0 docs only) | |

No existing `.lua` file is changed on this branch. TycoonCore, the save and the CLAIMLOAD block are untouched.

## Test counts

Measured on `main` `f6a546f` and again after B0 (B0 changes docs only; same counts):

| Suite | Checks passed | Mutation runs caught |
|---|---|---|
| tools/daily_test.py | 2,730 (0 failed) | 282 of 282 |
| tools/hud_test.py | 1,072 (0 failed) | 94 of 94 |
| tools/world_test.py | 350 | 82 of 82 |
| tools/icon_test.py | 371 | 68 of 68 |
| tools/shop_ux_test.py | 6,300 | 101 of 101 |
| tools/lobby_test.py | 27 | 26 of 26 |
| tools/building_test.py | none (lost before its first run) | none |

The suites were **not** run after the three B1 files were added. Several existing suites scan every root `.lua` file (daily_test.py around lines 7058, 7156, 8045, 8219, 8367; hud_test.py:1635; icon_test.py:1553; shop_ux_test.py:2691, 2811), so run all of them before building on these files.

## How to continue

```
git fetch origin
git worktree add ../lobby-all-v1 origin/lobby-all-v1
cd ../lobby-all-v1
LUAU=/path/to/luau python3 tools/daily_test.py   # then hud_test, world_test, icon_test, shop_ux_test, lobby_test
```

Next: rewrite `tools/building_test.py` (fake Roblox, named checks, mutants caught by name), make the three B1 modules pass it, then L2.
