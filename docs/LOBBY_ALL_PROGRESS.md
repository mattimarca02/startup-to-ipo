# lobby-all: progress (the running task list)

Branch `lobby-all`, from `main` `f6a546f`, in its own worktree. Never merged into `main` by this work; no pull request into `main`. Each stage ends with a tag, pushed with the branch (fast-forward only).

| Stage | Tag | What | State |
|---|---|---|---|
| B0 | `lobby-B0` | docs/BUILDING_STAGES_PROPOSAL.md, docs/MODEL_ASSETS_PLAN.md, docs/previews/buildings_plan.svg | done |
| B1 | `lobby-B1` | model slots (`ModelSlots`), building data and builder (`PlotBuilding`, `PlotBuildingVisuals`) with the Garage, `tools/building_test.py`; new files only, not wired | next |
| L2 | `lobby-L2` | permanent closed building in TycoonCore (`buildGarages`, reset on leave, garage sign), `BuildingClient` (fade, garage frame), solid outer walls | to do |
| L3 | `lobby-L3` | the claim behind `LobbyConfig.ClaimEnabled` (off): `claimGarage` with the moved CLAIMLOAD block, states, prompts, `UserId` hold, Free room, receipts, `LobbyClient` | to do |
| L4 | `lobby-L4` | the ring and the plaza (only with the claim on), persistent shells | to do |
| B2-B5 | `lobby-B2` ... `lobby-B5` | Small Office, Big Office, Small Corporate, Big Corporate | to do |
| L5 | `lobby-L5` | docs, README, the one Studio list (docs/STUDIO_SYNC_LOBBY.md), claims released | to do |

## How to continue

```
cd /path/to/repo && git fetch origin --tags
git worktree add ../lobby-all origin/lobby-all     # or: cd ../lobby-all && git pull --ff-only
cd ../lobby-all
LUAU=/path/to/luau python3 tools/daily_test.py      # and hud_test, world_test, icon_test, shop_ux_test, lobby_test, building_test
```

Then take the first stage marked "next" or "to do" above, claim its files in CONTRIBUTING.md (rows set to `@mattimarca02 (Claude Code) | lobby-all`), build, run every suite, commit, tag `lobby-<stage>`, `git push origin lobby-all --tags` (never `--force`).
