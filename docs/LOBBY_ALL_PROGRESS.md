# lobby-all: progress (the running task list)

Branch `lobby-all`, from `main` `f6a546f` (the latest `origin/main` on 2026-10-16), worktree `../lobby-all`. It builds what is left of docs/LOBBY_GARAGE_PROPOSAL.md (stages L2, L3, L4, L5, in that order) plus the five buildings made from the 3D kit (docs/KIT_MODELS.md). It ends with a pull request into `main` that is **not merged** by this work. A new session resumes from this file: take the first stage that is not "done".

| Stage | What | State |
|---|---|---|
| setup | `origin/kit-models` merged first, then `origin/building-pass` (CONTRIBUTING conflict: both sides' rows kept); claim rows for every file this branch edits | done |
| L2 | permanent closed building: `buildGarages`, the Floor in the garage, the garage sign, reset on leave; the five kit buildings (PlotBuilding, PlotBuildingVisuals), `BuildingClient` at the root, `tools/building_test.py` | done |
| L3 | the claim behind `LobbyConfig.ClaimEnabled` (ships false): `claimGarage` with the moved CLAIMLOAD block, states, prompts, `UserId` hold, Free room, receipts, `LobbyClient`, `tools/lobby_test.py` | done |
| L4 | the ring and the plaza (`LobbyConfig.Garages`, WorldVisuals ring layout), persistent shells | done |
| L5 | docs (CLAUDE.md, ROADMAP.md, README, PUBLISH_RULES), docs/STUDIO_SYNC_LOBBY.md (the one Studio list), claims released, pull request | next |

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
7. **Pieces in front of the facade** (plants, door leaf, columns, pillars, the bulb) stay before z 40 (WorldArt's `plotReach.front`; Small Corporate's revolving door is a vestibule from z 30 to 40, so it stays out of the room's walking-lane zone) and out of the lane, the apron and the claim post's spot (x 6 to 10, z 34.2 to 36.2: L3's post 3 studs outside the front wall at x +7, and its lamp).
8. **Upper stories** are exterior only: a hollow shell over a ceiling slab. Big Corporate is a one-story podium on the whole footprint with a 5-story tower (48 x 32) on top, so it fits the 160-part budget.

## Problems found in the plan (with the fix used, each one data only)

- **P1. WallDoor's opening is 6 wide; the doorway must be at least 9.** The kit may not be stretched. Fix: the solid doorway stays 9 wide (boxes at x +-4.5); the WallDoor mesh's jambs stand 1.5 studs into it on each side, non-solid (a player walking off-center goes through 1.5 studs of door frame). Alternative if the owner prefers: no WallDoor, a plain 9-wide opening with a RoofEdge lintel (one line per stage in PlotBuilding).
- **P2. Big Corporate's BoardTable (8 deep), Rug (8 deep) and Bell (6 deep) cannot stand in a band 4 deep.** Fix: Big Corporate's back band is 8 deep (z -40.2 to -32.2, still outside the room and every zone); its side bands stay 4. Alternative: leave those three out (one line).
- **P3. Small Corporate's "two short pillars":** the kit has no short pillar and pieces may not be scaled. Fix: two `Corner` pieces (2 x 2 x 14) beside the revolving door.

## L2: done (what it built)

- **TycoonCore** (5 edits, listed once in `tools/lobby_test.py` `L2_EDITS` and applied from there): the building modules required in pcall; `Workspace.Garages.Garage1..6` built at server start (`buildGarages`: the Floor, the stage 1 building, a hidden name sign); `syncBuilding` (every second through `syncRoom`, in pcall; a new building moves anyone standing in a new solid box to the landing); `setGarageSign` replaces the per-join billboard; `resetGarage` after the leave save (stage 1 Floor and building, no name); a Studio-only Debug button "Building: next stage" (in memory, never saved). Nothing between the CLAIMLOAD markers changed.
- **PlotBuilding** (data and pure layout): the 36-key `KitManifest` (copied from docs/KIT_MODELS.md, checked against it), a Parts fallback per key (every role, exactly the kit size), per-stage styles (color and material per role), the five layouts, the solid boxes, the furniture footprints.
- **PlotBuildingVisuals:** the builder (kit MeshParts only, recolored by Role, placed by WorldPivot, `KIT_FRONT_TURN`, only Wall/RoofEdge/Floor stretched; Parts fallback per piece with one warning per server), `sync`, `unstick`, `checkKit` (for the Studio command), `check`. BUILDINGMATH unchanged from building-pass except the comments.
- **BuildingClient** moved to the root; it checks the character in the garage's frame (the `Frame` attribute) and fades only the `Fade` group (glass from 0.3).
- **ShopClient:** one Debug row. docs/STUDIO_SYNC_SHOP.md's ShopClient row kept current (shop_ux_test checks it).
- Tests: `tools/building_test.py` rewritten for the kit (data, 5 stages x 4 turns x 3 kit modes, math, client, TycoonCore's garage code, source pins); daily_test's Floor regex, plotFrame sites and wiring checks; world_test's Floor regex; lobby_test's outside check (L1 + L2 edits), L1 doc history against `f6a546f`, the new "Lobby all" doc section, 5 L2 mutants.
- Counts after L2: daily 2,803 checks / 281 mutants; hud 1,072 / 94; world 350 / 82; icon 371 / 68; shop_ux 6,300 / 101; lobby 43 / 31; building 1,218 / 28. All pass.
- Found while building: the revolving door (10 deep) can't straddle the facade without entering the room's walking-lane zone, so it is a vestibule in front (z 30 to 40). The ring plaza (L4) must stay at or under 480 parts so six garages at their biggest stage plus the plaza stay under 3,000 (6 x (257 room + 153 building + 2)).
- Not verified (Studio only): the kit's real front direction (`KIT_FRONT_TURN`), that MeshPart sizes stretch as computed, the look of the five buildings, Roblox's camera with the invisible boxes, phone frame rate.

Next: L3.

## L3: done (what it built)

- **LobbyConfig** (new, ReplicatedStorage): `ClaimEnabled = false`, the row of garages (today's numbers), the plaza numbers, the claim post spot, distances, timings, the texts, and the one pure rule `canClaim(state, request)` (switch, rate, one claim per account and "still saving", slot, owner and Closing, distance).
- **TycoonCore** (7 edits, `L3_EDITS` in tools/lobby_test.py; the file is regenerated from `99eed7b` plus every edit, then the three marker comment lines): the join only enters the plaza (`inPlaza` before any yield; an already-here check, so the startup loop and PlayerAdded can never set one player up twice); `claimGarage` writes the claim (keyed on the UserId, held until that account's leave save returns), `plotOwners`, the state and the `Garage` attribute before anything yields, then the CLAIMLOAD block, untouched and still in place; the prompt's `requestClaim` (no yield between check and claim); `autoClaim` while the switch is off (today's behaviour; with no free garage it waits on the plaza, then the old kick after 60 s); the plaza fallback for a far spawn (claim on); the cap kicks only above 6 players; a startup warning when Max Players is above 6; states Free / MovingIn / Taken / Closing (attributes); the claim post (prompt, FREE sign, lamp; only with the claim on); the Free room (today's new-player room) in every free garage; `claimedAt` for ShopServer.
- **ShopServer:** a receipt waits with no deadline while the player has no garage, 30 s from the claim; the lounge door tells a player with no garage "Claim a garage first: your passes load with your company" and prompts nothing.
- **IpoClient, ShopClient:** a quiet wait for leaderstats (no "infinite yield"); ShopClient's Robux buttons say "Claim garage" and never prompt while `Garage` is 0. **LobbyClient** (new): the banner and a marker over the nearest Free garage, only with the claim on and no garage.
- Tests: `tools/lobby_test.py` now runs the **whole real TycoonCore** in a fake Roblox (`tools/lobby_runtime.luau`: a coroutine scheduler with simulated time, a DataStore with delays and failures, players who join, leave, rejoin and get kicked) for every case of the plan's L3 list, and the real LobbyClient (`tools/lobby_client_test.luau`); 17 claim mutants and 3 client mutants. hud_test follows the load into `claimGarage` (plus "leaderstats made at the claim"), shop_ux_test knows the new toast texts and tests the "Claim garage" buttons, daily_test and building_test follow the new plotFrame sites and the Free garage.
- Found while building: if the startup loop and PlayerAdded both called the join for one player, the second call would have waited in the auto-claim and kicked them after 60 s; the join now returns at once for a player it already has (tested).
- Not verified (Studio only): Roblox's own prompt-distance check, whether `ProcessReceipt` may wait that long, the claim with 2 and 3 real clients.

Next: L4.

## L4: done (what it built)

- **Decision:** the ring is used **only while `ClaimEnabled` is on** (`LobbyConfig.garages(claimEnabled)`): with the switch off (as it ships) the garages stay in today's row and no world is built, so a publish with the switch off moves nothing for live players. Turning the claim on brings the plaza, the ring and the claim together (one switch).
- **LobbyConfig.Ring:** the six garages of docs/LOBBY_GARAGE_PROPOSAL.md 4.2 (west facing +X, north facing -Z, east facing -X), each floor's front-center 95 from the plaza's center, lots 7.4 apart (6.4 per axis at the corners).
- **TycoonCore** (4 edits, `L4_EDITS`): with the claim on, `plotCenter` and the garages' turns come from the ring; the landing asks `RequestStreamAroundAsync` (in pcall) first; at server start, with the claim on, the plaza world is built once from WorldArt and WorldVisuals (in pcall: a broken world never stops the game).
- **WorldVisuals:** `ringSite` (turned garages, the moved spawn pad), `ringLayout` (the plaza around the spawn pad, a walk from each door, the forecourt to the lounge, a number sign, a lamp and two bushes per garage, four lit lamps, benches, planters, the arch, trees), keep-outs turned with each garage (its whole lot; in front of its facade, flat paving only), the "connected" check for turned fronts, the ring's own budget (480 parts). **WorldArt.Ring:** the numbers, some copied from PlotBuilding and LobbyConfig (compared by the tests). **PlotBuildingVisuals:** each building Model is Persistent (in pcall).
- **Pictures:** docs/previews/ring_topdown.svg (tools/render_previews.py): the ring with lots, floors, doors and the stage 1 and stage 5 footprints.
- Tests: world_test's ring program (16 checks: copied numbers, lots apart and on the Baseplate, every garage facing the plaza, the front line at 95, every named world check, the budget and lights, no tall part in any doorway lane, a part dropped in a lot is reported) and group R (11 mutants); lobby_test's runtime follows the ring with the claim on (3 more mutants: the ring with the claim off, the turns ignored, plotCenter ignoring the ring); daily_test and world_test's patch tests get a row stub for `LobbyConfig`; building_test checks the Persistent mode.
- Counts after L4: daily 2,813 / 281; hud 1,073 / 95; world 366 / 93; icon 371 / 68; shop_ux 6,306 / 103; lobby 112 / 55; building 1,220 / 29. All pass.
- Not verified (Studio only): StreamingEnabled and its radii, `ModelStreamingMode = Persistent` from a script, how the plaza looks, the walk from the spawn to each door on a phone.

Next: L5.

## How to continue

```
cd ../lobby-all && git pull --ff-only
LUAU=~/.local/luau-dl/luau python3 tools/building_test.py    # and daily, hud, world, icon, shop_ux, lobby
```
Then take the first stage marked "next" above, commit, push (`git push origin lobby-all`, never `--force`), and update this file.
