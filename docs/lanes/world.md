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

waiting for review of PR #37

## Last PR

PR #37 (`world-ring-plaza`): https://github.com/mattimarca02/startup-to-ipo/pull/37

## Last report

2026-10-17. I filled the backlog (7 items) and built item 1. PR #37 turns the ring's plaza (only drawn with `LobbyConfig.ClaimEnabled` on) from one flat slab into a garden. It has a paved square around the spawn pad and four spokes out to a promenade along the garages. Every garage walk now joins the promenade. Each quarter has a lawn bed with kerbs, trees, bushes and flowers. A fountain stands on the north spoke, and lamps and benches line the spokes. It uses 336 parts (budget 480) and 4 lights. The row (claim off, as it ships) does not change.

Tests (Luau 0.742): world 380 checks, 101 of 101 mutants caught (a new "ring garden" section with 8 checks and 8 new mutants). daily, hud, icon, shop_ux and building all pass. **lobby: 148 passed, 6 failed** (64/64 mutants). All 6 are old hashes of WorldArt and WorldVisuals pinned in docs/STUDIO_SYNC_LOBBY.md. Gameplay's `gameplay-lobby-test-history` (the ux lane's R1, and my request 1) fixes them. world_test.py no longer pins docs/STUDIO_SYNC_WORLD.md to the current files: it checks it as history at `98cc7a9`, and a newer file against the Studio steps row below.

Studio steps: below (paste WorldArt and WorldVisuals; nothing visible with the claim off). Requests: 1 to gameplay (same as ux R1), 2 to quality (none needed if 1 is done). Waiting for the owner: the review and merge of PR #37, after gameplay's lobby_test fix is merged (then I rebase and re-run all suites).

## Requests to other lanes

1. **gameplay (tools/lobby_test.py): the same as the ux lane's R1, which gameplay has claimed (`gameplay-lobby-test-history`).** `lobby_test.py` checks that docs/STUDIO_SYNC_LOBBY.md's "Lobby all" rows give the *current* SHA-256 of `WorldArt` and `WorldVisuals`, so any world PR fails 6 lobby checks, all about that doc (two table rows, two hash block rows, the block's two "ALL OK" runs). Once that section is checked as history (at `2df1410` or `98cc7a9`: WorldArt and WorldVisuals are the same in both), please let a file that changed since be checked against its lane file's "Studio steps" row, as world_test.py now does for docs/STUDIO_SYNC_WORLD.md (`SYNC_HISTORY`, `LANE_FILE`, `history_bytes`). Until it is merged, the lobby suite on `world-ring-plaza` reports these 6 failures (148 passed, 64 of 64 mutants caught) and nothing else.
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
