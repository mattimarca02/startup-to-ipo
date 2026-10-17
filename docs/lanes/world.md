# Lane: world

Only the world lane edits this file. See docs/LANES.md.

## Backlog (in order)

1. **Ring plaza garden** (branch `world-ring-plaza`, this run): the 180 x 180 plaza is one flat slab today. Split it into a paved square around the spawn pad, four spokes, a promenade along the garages' fronts that every walk joins, four lawn beds with kerbs, trees, bushes, planters and benches, a fountain on the north spoke, lamps along the spokes. Ring only (claim on); the row (claim off) does not change. Within `Budget.ringParts` (480) and 6 lights.
2. **Around the VIP Lounge (ring)**: the lounge stands south of the plaza, alone on the grass. A garden round its three closed sides (hedges, trees, a back path), lamps at the forecourt, all outside the lounge margin, door clear zone and drop spot.
3. **Ring outskirts**: trees and bushes behind and between the garages (outside every lot and its reach), an outer loop path so the ring reads as a town block, the hills moved to frame the ring view from the plaza.
4. **Kit furniture outdoors** (`LobbyTree`, `Plant`, `BareBulb` from `ReplicatedStorage.KitModels`, docs/KIT_MODELS.md): pieces that clone a kit MeshPart when it is there and build the Parts piece when not, one warning per server. The world checks must learn MeshParts (no collision, touch or query; size from `KitSize`). Needs the building lane's kit keys to stay as they are (no request yet).
5. **World icons over the ring**: an icon over each garage's door and the lounge (IconArt/IconVisuals), readable on a phone at plaza distance, hidden inside a garage.
6. **Phone pass for the whole world**: part and shadow counts per area, streaming (Atomic models), the far hills' cost, measured against the building budget (3,000 parts with six Big Corporate garages); row and ring.
7. **Row world refresh (claim off)**: bring the row's street decor to the ring's style, only if the claim stays off for long (owner decision 9).

## Doing now

world-ring-plaza - started 2026-10-17 15:54 UTC

## Last PR

none

## Requests to other lanes

1. **gameplay (tools/lobby_test.py), blocks a green lobby suite on every world PR.** `lobby_test.py` checks that docs/STUDIO_SYNC_LOBBY.md's "Lobby all" table and hash block give the *current* SHA-256 of `WorldArt` and `WorldVisuals` (`ALL_SCRIPTS`, "changed"). Any change to those two files (only the world lane edits them, and the quality lane owns the doc) fails 6 lobby checks, all about that doc: the two table rows, the two hash block rows, and the block's two "ALL OK" runs. The same will happen to the building lane with `PlotBuilding`, `PlotBuildingVisuals` and `BuildingClient`, and to the ux lane with `LobbyClient`, `ShopClient` and `IpoClient`. Asked: treat the "Lobby all" section as history, like the L1 section (`L1_COMMIT`): compare its rows with the files at `98cc7a9` (main before the lanes), and for a file that changed since, check the owning lane file's "Studio steps" row instead. world_test.py does exactly this for docs/STUDIO_SYNC_WORLD.md since `world-ring-plaza` (`SYNC_HISTORY`, `LANE_FILE`, `history_bytes`). Until then the lobby suite on `world-ring-plaza` reports these 6 failures (148 passed, 64 of 64 mutants caught); nothing else in it fails.
2. **quality (docs/STUDIO_SYNC_LOBBY.md, docs/STUDIO_SYNC_WORLD.md).** No edit needed if request 1 is done; the two docs then stay as history and the new hashes come from the lane files into docs/STUDIO_SYNC_BATCH.md. If the owner prefers the docs kept current instead, the two rows to write are in "Studio steps" below.

## Studio steps (merged PRs not yet in Studio)

none merged yet. **When `world-ring-plaza` is merged** (the quality lane copies this into docs/STUDIO_SYNC_BATCH.md):

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `WorldArt` | ModuleScript, ServerScriptService | changed | `7c24e992b60c6319f309dbd7dfda2cafa201566afece96ddc5678e9d87c57d8f` | 17648 |
| `WorldVisuals` | ModuleScript, ServerScriptService | changed | `3547afbbecd30e01f65285b1c483932da30751db9fa328119a267126c7563a90` | 59866 |

1. Paste `WorldArt.lua` over `ServerScriptService > WorldArt` and `WorldVisuals.lua` over `ServerScriptService > WorldVisuals` (both already exist). No new object, no other script changes.
2. Nothing changes while `LobbyConfig.ClaimEnabled` is off (it ships off): the garden is drawn only with the ring. To see it in Studio, set `ClaimEnabled = true` in `ReplicatedStorage > LobbyConfig` **for the playtest only** (docs/STUDIO_SYNC_LOBBY.md says how), press F5, walk the plaza: the paved square, four spokes, the promenade along the garages, four lawn beds, the fountain north of the spawn, benches and lamps. Output must show no red error and no `World` warning. Then set it back to `false` before any publish.
3. Phone: Test > Device, a phone; the plaza should stay smooth (336 world parts, 4 lights).
