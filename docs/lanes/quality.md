# Lane: quality

Only the quality lane edits this file. See docs/LANES.md.

## Backlog (in order)

1. Review every open lane PR (verdicts below); a new head needs a new verdict.
2. After merges: CLAUDE.md, README.md, ROADMAP.md from the merged PRs, and docs/STUDIO_SYNC_BATCH.md (branch `quality-docs-batch`, claimed).
3. Stale branches and PR #16 (recommendation below; nothing deleted).

## Doing now

idle (last run 2026-10-17 17:10 to 18:05 UTC: the manager's review of #35, #36, #37)

## Verdicts

Every PR was run with all seven suites (Luau 0.742), on its head and merged with main 05dc382; and #35 + #36 + #37 + #38 merged together on main.

- PR #35 (ux, head 2f98a40): **MERGE.** All seven pass merged with main: daily, hud 1073 checks + 69/69 mutants + claim button 117 checks and 21/21 mutants, world 366 + 93/93, icon 371 + 68/68, shop_ux 6306 + 103/103, lobby 154 + 64/64, building 1278 + 40/40. Only ux files (ClaimButtonClient.lua new, tools/claim_button_test.luau new, tools/hud_test.py), all claimed by ux. Display only: no remote, no server change, stops on its first line with `ClaimEnabled` off. It is 21 commits behind main (lane files and #34 only), merges cleanly; rebase before the merge (LANES.md). Not blocking, for a later ux PR: ClaimButtonClient.lua:154-165 keeps one `shownPrompt`; if two claim prompts show for touch at once and the newer one hides first, the button hides while the other is still shown. Keep a set of shown prompts and show the nearest.
- PR #36 (building, head 57085b7): **MERGE, after #38.** No conflict with #34: it is rebased on it and builds with `KIT_FRONT_TURN = 180` (PlotBuilding.lua:28); building_test builds with 0 and 180. The Studio hash in the PR and in docs/lanes/building.md is the right one (PlotBuilding f04e3b89486a4b8a3656633029412c1e666df84432c9760639e89c9361ea5788, 42603 bytes; PlotBuildingVisuals 2e956d55..., 27493 bytes). building 1407 + 46/46; daily, hud, world, icon, shop_ux pass. On its own, lobby has 6 failures (the "Lobby all" pins of PlotBuilding and PlotBuildingVisuals in docs/STUDIO_SYNC_LOBBY.md); with #38 merged in, lobby is 155 checks, 63/63 mutants, green. So merge #38 first. Only building files. Blocks are never solid (fallback flags), signs are Parts only.
- PR #37 (world, head faa7fa9): **MERGE, after #38.** faa7fa9 is the same change as 155529e (rebased). world 380 + 101/101; daily, hud, icon, shop_ux, building pass; lobby 6 failures alone (WorldArt and WorldVisuals pins), green with #38. Only world files. Follow-up for the world lane (not blocking): tools/world_test.py:1298-1313 looks for a changed file's hash only in docs/lanes/world.md "Studio steps". When that row moves into docs/STUDIO_SYNC_BATCH.md and the lane file says "none", world_test turns red on main (lane files are pushed without tests). Either keep the row in world.md until the next world change, or let the check also accept the row in docs/STUDIO_SYNC_BATCH.md.
- Merge order: **#38, then #36 and #37** (any order, each rebased), and #35 at any time.
- Test note (ux lane, tools/hud_test.py:1728, not blocking): the HUD mutant "event not disconnected" uses about 3 GB of memory. With several suites running at once the Linux OOM killer stops it and it shows as "MUTATION CRASHED ... no output" (68 of 69). Run alone it is caught (69 of 69) on main and on every PR. A cap on the scenario's loop or a smaller fake would make it stable.

## Last PR

none

## Last report

2026-10-17, second run (manager's request: review #35, #36, #37). All three are fit to merge: #35 now; #36 and #37 once gameplay's PR #38 (lobby_test checks the "Lobby all" section as history) is merged first, which removes their only failures (6 lobby doc checks each). #36 does not conflict with #34 and builds with KIT_FRONT_TURN = 180; its Studio hashes are current. Two small follow-ups go to their lanes: ux (the two-prompts case, and a hud mutant that runs out of memory when the machine is busy), world (world_test reads hashes only from the lane file). No docs PR yet: no lane PR is merged, so CLAUDE.md, README and the Studio batch have nothing new to take. In the first run my push to main was refused, so the verdicts were only in that run's report. Nothing was merged or deleted.

## Requests to other lanes

- **To gameplay:** PR #38 is what #36, #37 and #40 wait on; it is green with them merged on top.
- **To ux (later):** the two-prompts case of ClaimButtonClient and the memory-heavy hud mutant (Verdicts above).
- **To world (later):** world_test's hash check should also accept docs/STUDIO_SYNC_BATCH.md (Verdicts above).

## Stale branches (recommendation for the owner; nothing deleted)

- PR #16 (`docs-contributing-stale-claim`): close it. Main already marks tools/economy_sim.py and docs/ECONOMY.md free.
- Fully in main, safe to delete: lanes-setup, lobby-all, kit-models, lobby-l0, lobby-l1, lobby-garage, master-fix, integration-1, integration-2, shop-build, hud-cash, task-needs-desk, world-icons-pass, gameplay-design, customize-pr1, design-sims-fixes, sims-two-sectors-clean, design-customize, visuals-garage, building-pass, test-gap-fixes, pr1-task-engine, active-loops, launch-decisions, kit-front-180 (merged in #34).
- Look first: design-tutorial (docs/TUTORIAL_PROPOSAL.md not on main), content-bible (docs/CONTENT_BIBLE.md not on main), income-rejoin-investigation (docs/reviews/INCOME_REJOIN_INVESTIGATION.md not on main): merge the doc or drop it. lobby-all-v1 (half-done, replaced by lobby-all) and sims-two-sectors (replaced by sims-two-sectors-clean): delete. claude/prepublish-*, claude/pr14-*, claude/m6-review: older versions of docs that are on main: delete. claude/full-review shares no history with main: keep only if its review text is wanted.

## Studio steps (merged PRs not yet in Studio)

none (no lane PR merged yet)
