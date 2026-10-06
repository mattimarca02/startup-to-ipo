# Shop build (S1 and S2): notes and progress

Branch `shop-build` (from `world-icons-pass` at `6bc827c`), worktree `../shop-build`. Builds PR **S1** and **S2** of docs/SHOP_UX_PROPOSAL.md section 5, nothing else: no S3 (no icons, no IconArt or IconVisuals, ShopClient keeps its emoji), no S4, no S5. No Studio, no MCP: everything was written and tested outside Studio, with the free `luau` command-line tool and fake Roblox objects.

## Progress (the source of truth when this job is resumed)

Each item is one commit, pushed right after (`git push -u origin shop-build`), after `tools/daily_test.py`, `tools/shop_ux_test.py` (once it exists), `tools/icon_test.py` and `tools/world_test.py` all pass. An item is ticked in the same commit that does it.

**Phase 0: set-up**
- [x] 0.1 Claim the files in `CONTRIBUTING.md` (ShopClient, tools/daily_test.py, README.md; new rows ShopLayout, tools/shop_ux_test.py, docs/STUDIO_SYNC_SHOP.md, these notes)
- [x] 0.2 These notes with the checklist

**Phase 1: S1 (layout, accessibility, the Names, help, strip, status line)**
- [ ] 1.1 `ShopLayout.lua` (new, pure): `layout(guiW, guiH, topBar, ...)` and the card geometry
- [ ] 1.2 `ShopClient.lua` S1: the layout from ShopLayout (landscape rail, portrait row), 44 px header items and tap targets, 16 px minimum text, the Names, `HelpButton` and its card, `TutorialStrip`, the in-window status line
- [ ] 1.3 `tools/shop_ux_test.py` (new): the fake Roblox and the S1 checks
- [ ] 1.4 S1 mutants
- [ ] 1.5 README rows for `ShopLayout.lua` and `tools/shop_ux_test.py`

**Phase 2: S2 (the Office ladder)**
- [ ] 2.1 `ShopLayout.lua`: ladder state, bar fill, time text, best value, row and hero geometry
- [ ] 2.2 `ShopClient.lua` S2: the Office ladder
- [ ] 2.3 `tools/daily_test.py`: "daily_test: Locked check follows the new ladder" (the one edit there)
- [ ] 2.4 `tools/shop_ux_test.py`: the S2 checks
- [ ] 2.5 S2 mutants (at least 40 in all, each caught by a named check)

**Phase 3: Studio sync and wrap-up**
- [ ] 3.1 `docs/STUDIO_SYNC_SHOP.md` (paste order, SHA-256 and sizes, playtest checklist)
- [ ] 3.2 These notes complete (deviations, questions, what was not tested, results)
- [ ] 3.3 Release the claims (rows kept, set to free)

## Preconditions (checked 2026-10-06, before any change)

1. `docs/SHOP_UX_PROPOSAL.md` on `origin/world-icons-pass` (`6bc827c`) records the six owner decisions as **DECIDED BY THE OWNER**: the landscape tab rail (3.1), all six Office rungs with the summary row, hero card and "Unlocks after X" (3.2), Office upgrades never ask for a confirmation and the two-tap confirm only for buildings and furniture above half the player's Cash (3.2, 3.3), factual badges only (3.3), the details sheet sliding up inside the shop window (3.3), 3D icons only for the Office upgrades and the creatures, drawn shapes for the rest (3.6). **Holds.**
2. On this branch the claim rows of `docs/SHOP_UX_PROPOSAL.md`, `docs/WORLD_ICONS_NOTES.md` and `ShopClient` were free. **Holds.**
3. `ShopClient` is free in the `CONTRIBUTING.md` of `origin/customize-pr1` (`3c548ec`), `origin/task-needs-desk` (`c825b14`) and `origin/hud-cash` (`9c15e20`); none of the three has any claimed row at all. Stale rows seen on older branches (they do not count): `ShopClient` on `claude/m6-review`, `claude/pr14-review`, `claude/pr14-rereview` (milestone-6-daily-rewards, 2026-10-01) and `docs-contributing-stale-claim` (milestone-5-onboarding); `tools/daily_test.py` on those three review branches, `building-pass` (visuals-garage, 2026-10-03) and `sims-two-sectors` (customize-pr1, 2026-10-05). **Holds.**
4. (Informational) `IconVisuals.lua` has the global ViewportFrame cap: one registry for the whole client (IconVisuals.lua:499), `allocate` reads `art.Style.viewportCap` (:599, IconArt.lua:48 = 8), and both `build()` (:665-679) and the caches' `show()` go through it. **Holds.** This job does not touch IconArt or IconVisuals.

## Tools

The container had no `luau`: the official release `luau-ubuntu.zip` (github.com/luau-lang/luau, latest) was downloaded into the session's scratch folder and used through `LUAU=/path/to/luau`. Nothing was installed in the repo.

## Results before any change (this branch at `6bc827c`)

| Suite | Checks | Mutation runs |
|---|---|---|
| `tools/daily_test.py` | 1,772 pass, 0 failed | 20 of 20 |
| `tools/world_test.py` | 298 pass | 65 of 65 |
| `tools/icon_test.py` | 199 pass | 51 of 51 |
