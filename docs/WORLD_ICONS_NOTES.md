# World and icons pass: notes and progress

Branch `world-icons-pass` (from `main` at `e3c9e67`), worktree `../world-icons`. New files only; the one existing-file edit is the claim rows in `CONTRIBUTING.md`. No Studio, no MCP: everything here was written and tested outside Studio, with the free `luau` command-line tool and fake Roblox objects.

## Progress (the source of truth when this job is resumed)

Each item is one commit, pushed right after. An item is ticked in the same commit that does it.

**Phase 0: set-up**
- [x] 0.1 Claim every new file in `CONTRIBUTING.md`
- [x] 0.2 This notes file with the checklist

**Phase 1: shop UX (docs only)**
- [x] 1.1 `docs/SHOP_UX_PROPOSAL.md` (3,409 words; 6 open questions)

**Phase 2: world pass**
- [x] 2.1 `docs/WORLD_PASS_PROPOSAL.md` (2,481 words; numbers re-checked after the build in 2.4)
- [x] 2.2 `WorldArt.lua` (pure data)
- [x] 2.3 `WorldVisuals.lua` (builder, named checks, pure geometry)
- [x] 2.4 `tools/world_test.py` (fake Roblox, checks, parameter sweep): 213 checks (154 in Luau, 59 source checks)
- [x] 2.5 World mutants, group A: 29 runs on `WorldVisuals.lua` (builder breakages and weakened checks), 29 caught by their named checks
- [x] 2.6 World mutants, group B: 24 runs on `WorldArt.lua` (data rules, copied numbers, Studio facts); 53 in all, every one caught by its named check
- [x] 2.7 `docs/world_pass_integration.patch` (not applied): two blocks in TycoonCore (10 lines after line 61, 12 before line 840); `tools/world_test.py` runs both blocks in the fake and, with `--integration`, both suites on a patched copy
- [ ] 2.8 World preview block (`Workspace.PREVIEW_WORLD`) in `docs/STUDIO_SYNC_WORLD.md`, run in the fake by the test

**Phase 3: icons**
- [ ] 3.1 `IconArt.lua` (pure data, style sheet)
- [ ] 3.2 `IconVisuals.lua` (builders, pure size, framing and lazy-creation functions)
- [ ] 3.3 `tools/icon_test.py`
- [ ] 3.4 Icon mutants, group A
- [ ] 3.5 Icon mutants, group B (20 or more in all)
- [ ] 3.6 Icon preview block (`StarterGui.PREVIEW_ICONS`) in `docs/STUDIO_SYNC_WORLD.md`, run in the fake by the test

**Phase 3b: previews (SVG text)**
- [ ] 3b.1 `tools/render_previews.py`
- [ ] 3b.2 `docs/previews/world_topdown.svg`
- [ ] 3b.3 `docs/previews/icons_sheet.svg`

**Phase 4: Studio sync and wrap-up**
- [ ] 4.1 `docs/STUDIO_SYNC_WORLD.md` complete (files, SHA-256 and sizes, steps, previews, delete list, what to look at)
- [ ] 4.2 These notes complete (judgment calls, OWNER CHOICE list, blocked items, risks)
- [ ] 4.3 Release every claim in `CONTRIBUTING.md`

## Studio facts (measured by the owner, not in the repo)

These are placed by hand in Studio. They are treated as fixed constants in `WorldArt.Site` (marked "Studio fact") and the tests use them as they are; nothing parses them from a `.lua` file because no script creates these two objects.

| Object | Size | Position | What follows |
|---|---|---|---|
| `Workspace.Baseplate` | 2048 x 16 x 2048 | (0, -8, 0) | its top is y = 0, it spans x and z from -1024 to 1024 |
| `Workspace.SpawnLocation` | 12 x 1 x 12 | (-1, 0.5, -1) | the pad covers x -7 to 5, z -7 to 5, y 0 to 1 |

The world builder never moves, resizes, replaces or deletes either of them, and nothing it builds covers the spawn pad. The Studio preview block reads both objects (read only) and prints whether they still match these numbers.

## Judgment calls

- **Shop proposal (phase 1):** the phone numbers use a 36 px Roblox top bar (GUI 667 x 339 and 320 x 532), the same assumption as TUTORIAL_PROPOSAL section 3; portrait's window is capped at 470 px tall, so the shop looks the same with a 0 px bar. Text widths (characters per line) are marked as estimates.
- **Shop proposal:** its future tests go in a new `tools/shop_ux_test.py`, not in `tools/daily_test.py` (other branches own that file).
- **Shop proposal:** Robux buys keep Roblox's own prompt as their only confirmation; the two-tap confirm is proposed for Cash buys above a threshold (open question 2).
- **World: the plots' reach.** The world keeps out of a box around each plot (36 studs to the sides, 50 behind, 40 in front of the center, 32 up), not just the 60 x 60 floor: today's rooms reach 35.5 to the sides (stage 1's dirt), 49 behind (stage 5's skyline) and 36.2 in front (stage 1's dirt), and the building pass (branch `building-pass`, not merged) puts ground pieces up to 40 in front. `tools/world_test.py` builds all five rooms and fails if one reaches past the box.
- **World: the front walks** are the only pieces that enter a plot's box: a flat strip from the floor's front edge to the front street, 0.1 stud above stage 1's yard dirt (so the two never flicker). If the building pass lands, its doorstep path lies under the walk's first studs.
- **World: the Studio preview rooms** (`PREVIEW_STAGES`, x -630 to -290) are a keep-out only at spacing 90: they were placed for it. At spacing 112 plot 1 itself would stand on them, so the preview snippet in docs/STUDIO_SYNC.md would have to move (to about x -700) first.
- **World: font.** The arch uses `FredokaOne`, not PlotArt's `LuckiestGuy`: the rule against the four odds words in strings also catches that font's name.
- **World: a missing palette color** builds bright magenta instead of stopping the build (a sector palette with a gap still gives a world); the `palette` check names the gap.
- **World: decor streaming.** Each decor item is its own Model with `ModelStreamingMode = Atomic`, set inside `pcall` (if a Roblox version refuses it from a script, the item keeps the default).

## OWNER CHOICE

(Defaults picked where the owner's taste decides; each one is implemented and can be changed in one place.)

## Blocked

(Nothing blocked so far.)

## Risks

(Filled in as the work goes.)
