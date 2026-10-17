# Lane: interiors

Only the interiors lane edits this file. See docs/LANES.md.

## Backlog (in order)

The furniture inside the 60 x 60 room, different at each funding stage, from the 3D kit (`ReplicatedStorage.KitModels`, docs/KIT_MODELS.md) recolored per stage, with a Parts version of every kit piece for when the kit is missing. No new models. Every PlotArt rule stays: gameplay positions and reserved zones, the six upgrade props unchanged, at most 260 parts and 3 PointLights per room (with the kit and without it), no odds text. Fingerprints change only on purpose and the PR says so.

1. **Kit furniture builder + the Garage (stage 1).** PlotVisuals builds "kit pieces" (a kit key, a spot, a quarter turn, a scale, a color and material per role) from KitModels, with the Parts fallback from `PlotArt.Kit`; validate and check cover them. The Garage gets: crates as hire desks (kit `Crate`), a workbench (`Workbench`), an old desk and chair for the founder (`Desk`, `Chair`, worn colors), the bare bulb (`BareBulb`). Stage 1 fingerprint updated on purpose.
2. **Small Office (stage 2, Seed).** Hire desks from the kit `Desk` with a `Computer` on each (scaled to the desk zone; no chairs for hires: a chair would stand where the hire stands), the founder's desk and chair from the kit, a kit `Plant` or two, mint/oak recolors.
3. **Big Office (stage 3, Series A).** As stage 2 plus a `MeetingTable` with chairs and a `Whiteboard`, brick-loft recolors.
4. **Small Corporate (stage 4, Series B).** Dark wood and gold recolors, `Laptop` instead of `Computer` on the hire desks, a `BoardTable` with chairs, `Shelf`, `Plant`.
5. **Big Corporate (stage 5, IPO-ready).** The same dark wood and gold, `Laptop`s, the `BoardTable`, `Armchair`s and a `Rug` in the lounge, `ReceptionDesk` if it fits outside every zone.
6. **Studio preview and checks.** A command-bar snippet (in this lane's Studio steps) that builds the five rooms with the kit next to each other, and a kit check of the furniture keys the rooms use.

## Doing now

interiors-kit-garage - started 2026-10-17 15:54 UTC

## Last PR

none

## Requests to other lanes

none

## Studio steps (merged PRs not yet in Studio)

none
