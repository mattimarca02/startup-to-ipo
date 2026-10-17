# Lane: building

Only the building lane edits this file. See docs/LANES.md.

## Backlog (in order)

Goal: the outside of the five buildings looks better, with every PlotBuilding rule kept (solid = only the invisible boxes, the 9 x 9 lane, the fade, the lot, 160 parts, no lights, the game works with no kit). Kit pieces (stretch rules apply) and plain Parts only.

1. **Garage: a crow-stepped pitched roof, a company sign and facade details** (PR `building-garage-roof`). The builder learns "Block" pieces (one plain Part, styled by role like the kit, the same flags as a fallback Part), so later items need no kit change. The Garage gets a rusty metal pitched roof with a ridge cap, brick crow-stepped gables front and back, a sign board over the roll-up door (an orange growth-chart emblem, no text), two front windows with sills, a concrete plinth, gutters and four downpipes.
2. **Small Office: a canopy over the door, a sign, a stepped parapet.** A flat canopy (Blocks) over the stretched WallDoor, the sign board on a raised parapet above it, window sills.
3. **Big Office: a sign band and floor lines.** A band between the two stories on all four sides, the sign over the entrance, pilasters between the window bays.
4. **Small Corporate: a real entrance.** A portico (a flat canopy over the 10-wide entrance on its two pillars, never solid, nothing in the lane), the sign on the crown band, vertical fins on the glass so the four stories don't read as one flat box.
5. **Big Corporate: the podium sign and tower details.** A sign on the podium over the entrance, a band on the podium's roof edge. Its budget is tight (152 of 160; six garages at 160 parts still stay under 3,000 with today's room and plaza).
6. **The company name on the sign** (needs other lanes: the name is CompanyServer's data, which the building does not read; a request to gameplay first, and only once the company is visible to players).

## Doing now

building-garage-roof - started 2026-10-17 15:40 UTC

## Last PR

none

## Requests to other lanes

none

## Studio steps (merged PRs not yet in Studio)

none
