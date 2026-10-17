# Lane: building

Only the building lane edits this file. See docs/LANES.md.

## Backlog (in order)

Goal: the outside of the five buildings looks better, with every PlotBuilding rule kept (solid = only the invisible boxes, the 9 x 9 lane, the fade, the lot, 160 parts, no lights, the game works with no kit). Kit pieces (stretch rules apply) and plain Parts only.

1. **Garage: a crow-stepped pitched roof, a company sign and facade details** (PR `building-garage-roof`). The builder learns "Block" pieces (one plain Part, styled by role like the kit, the same flags as a fallback Part), so later items need no kit change. The Garage gets a rusty metal pitched roof with a ridge cap, brick crow-stepped gables front and back, a sign board over the roll-up door (an orange growth-chart emblem, no text), two front windows with sills, a concrete plinth, gutters and four downpipes.
2. **Small Office: a canopy over the door, a sign, a stepped parapet.** A flat canopy (Blocks) over the stretched WallDoor, the sign board on a raised parapet above it, window sills.
3. **Big Office: a sign band and floor lines.** A band between the two stories on all four sides, the sign over the entrance, pilasters between the window bays.
4. **Small Corporate: a real entrance.** A portico (a flat canopy over the 10-wide entrance on its two pillars, never solid, nothing in the lane), the sign on the crown band, vertical fins on the glass so the four stories don't read as one flat box.
5. **Big Corporate: the podium sign and tower details.** A sign on the podium over the entrance, a band on the podium's roof edge. Its budget is tight (152 of 160; six garages at 160 parts still stay under 3,000 with today's room and plaza).
6. **(Owner request, high priority) the building cinematic** (docs/lanes/owner.md, 2026-10-17): crane and wrecking ball knock down the old building, the new one rises; client only, 5 to 7 s, skippable, never after an IPO, Blender preview frames in docs/previews/building/. Next after item 1.
7. **The company name on the sign** (needs other lanes: the name is CompanyServer's data, which the building does not read; a request to gameplay first, and only once the company is visible to players).

## Doing now

waiting for review of PR #36

## Last PR

#36 `building-garage-roof`: https://github.com/mattimarca02/startup-to-ipo/pull/36

## Last report

(2026-10-17) PR #36 gives the Garage a rusty pitched roof between brick gables stepped front and back, a sign board over the roll-up door (a growth-chart emblem made of Parts, no text), two front windows with sills, a plinth, gutters and downpipes. To do it the builder learned "Blocks": plain Parts styled by role with the same flags as fallback Parts, never a kit model. Solid boxes, lane, fade, lot and the other four stages are unchanged; the Garage is 88 parts. A before/after picture is in docs/previews/building/garage_roof.png. Tests: building 1407 passed with 46 of 46 mutants; daily, hud, world, icon and shop_ux all green; lobby_test has 6 expected failures (the STUDIO_SYNC_LOBBY.md hash checks for PlotBuilding and PlotBuildingVisuals), fixed by the ux lane's request R1 that the gameplay lane has claimed. Next: the owner's cinematic request (backlog item 6, done before items 2 to 5).

## Requests to other lanes

- **B1, to gameplay (tools/lobby_test.py):** the same as the ux lane's R1. PR #36 changes PlotBuilding.lua and PlotBuildingVisuals.lua, so the "Lobby all" hash checks against docs/STUDIO_SYNC_LOBBY.md fail (6 checks). Please pin that section to the lobby-all merge commit as R1 asks.
- **B2, to quality (CLAUDE.md, after #36 merges):** in the "garages and their buildings" rules, add one sentence: Blocks (PlotBuilding.BLOCK) are plain Parts for details the kit lacks (roofs, signs, sills, pipes), painted by role, with the same flags as fallback Parts; signs are Parts only, no text.

## Studio steps (merged PRs not yet in Studio)

none merged yet. When #36 merges: paste `PlotBuilding` (sha256 179825d759e85fce52554ead5dd0a1181f968338ecc6aef9d3bf6deeebb18e28, 42601 bytes) and `PlotBuildingVisuals` (sha256 2e956d553b0b5bd3ef51bf8db4b643634b86cca83111bdbe9fa7fec8405e5043, 27493 bytes) into ServerScriptService, then F5: the garage shows the roof and sign, walking in fades the whole shell, no new warnings. (If a Studio sync changes KIT_FRONT_TURN on main first, I rebase and give new hashes.)
