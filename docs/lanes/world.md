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

none

## Studio steps (merged PRs not yet in Studio)

none
