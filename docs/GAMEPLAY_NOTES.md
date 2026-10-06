# Gameplay first hour: working notes

Notes for `docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md` (branch `gameplay-design`, worktree `../gameplay-design`, started 2026-10-06). Docs only: no code, no Studio, no MCP. The only existing-file edit is the two claim rows in `CONTRIBUTING.md`.

## Progress

- [x] Worktree `../gameplay-design` from `origin/main` (e3c9e67), branch `gameplay-design`
- [x] Claim both docs in `CONTRIBUTING.md` (9f54c8d, pushed)
- [x] Read the docs and scripts listed in the brief (all found; see Sources)
- [x] Run `python tools/economy_sim.py` (default output, read-only; 5.5 s, exit 0)
- [x] Section 1: Audit
- [x] Section 2: The core loop
- [x] Section 3: The first 10 minutes
- [x] Section 4: The first hour
- [ ] Section 5: Game feel
- [ ] Section 6: Monetization that feels fair
- [ ] Section 7: Frustration and safety nets
- [ ] Section 8: Sectors
- [ ] Section 9: Measurement
- [ ] Section 10: What to build, in order
- [ ] Section 11: Open questions
- [ ] Word count at most 5,500 (`wc -w`)
- [ ] Release both claims in `CONTRIBUTING.md`

## Sources

Where each input came from (main = `origin/main` at e3c9e67).

| Input | Read from |
|---|---|
| Scripts, configs, ROADMAP, ECONOMY, LONG_GAME, ACTIVE_LOOPS, PLOT_VISUALS, PUBLISH_RULES, STORE_PAGE, FULL_REVIEW | main |
| CUSTOMIZE, FUNDING_ROUNDS, SECTORS proposals | `origin/design-sims-fixes` (on main too, but design-sims-fixes is newer: it records the owner's four decisions of 2026-10-05) |
| TUTORIAL_PROPOSAL | `origin/design-tutorial` |
| CONTENT_BIBLE | `origin/content-bible` |
| SHOP_UX_PROPOSAL, WORLD_PASS_PROPOSAL | `origin/world-icons-pass` |
| The Desk rule for calls | `origin/task-needs-desk` (TaskConfig, TaskServer, TaskClient diff) |
| SIMS_RESULTS (S1-S10) | `origin/sims-two-sectors-clean` (extra, not in the brief: used for S10 cadence) |
| Sim numbers | `python tools/economy_sim.py` on this worktree (main), default output only |

## Judgment calls

1. **Two builds.** The audit describes `main` as it is ("today": live servers have no calls). Sections 3-4 design the **launch** build: LONG_GAME PR 2 (owner's direction: first IPO after 50+ engaged hours, LG:3), calls from the Desk on, the tutorial, sectors, rounds. Today's 12-minute first IPO is treated as a finding, not as the target.
2. **Scratch model.** `economy_sim.py` has no free egg, no calls and no Day 1 gift, and its default run uses today's prices. I wrote a small model outside the repo (same config numbers; LONG Garage prices read from `LONG_ITEMS`, economy_sim.py:1067-1077) with human delays as estimates: Desk at 0:30, a ready egg noticed in 20 s, purchases 5 s after they are affordable, 80% of calls answered, egg hires at their average Income ($4.97/s Garage, $3/s for LONG's planned Coding Cat). Every model number in the proposal is marked as an estimate.
3. **Checked and dropped:** I suspected that keeping a window open for 90 s starts quiet mode the moment it closes. It doesn't: `settle` moves the idle clock while paused (TaskServer.lua:232).
4. **LG R3** (poaching needs 14+ days of account age and 10 engaged hours, LG:108) is treated as proposed, not decided: LG:128 lists R1 and R2 among the decisions, not R3.
5. **A third Garage desk.** Model G (cheaper first items only) still left a 10-minute wait from 8:00 to the Server Rack. Adding Desk 3 and a Bug Beetle egg (model G2) brings the longest wait in minutes 0-20 to about 6 minutes, and it also fixes the free-egg conflict (the free hire takes Desk 1 in LONG's list, which assumes the first hire is bought).
6. **The Day 1 gift goes after minute 10, not at 7:00.** At 7:00 the $4,200 gift would buy Desk 3 and an egg at once and leave an 8-minute wait after it; after the third hire (~12:20) its ~$6,600 shortens the longest wait instead.
7. **Findings about today that LONG PR 2 fixes** (A4, A5, A20) are kept in the list, marked "(today)" and "planned", so the owner sees what a launch on today's code would feel like.

## OWNER CHOICE

Defaults picked where the owner's taste decides. Each one is marked in the proposal too.

| # | Default picked | Where it is decided later | Section |
|---|---|---|---|
| 1 | The very first founding shows the sector picker (D-C) with **Software preselected**, because both sectors are "not done" for a new player (CUST 1.3) and Software teaches the shared engine | `SectorConfig` / the picker (CUST PR 4) | 3, 8 |
| 2 | The cheaper first Garage items are paid back by raising the **Whiteboard and Neon Logo**, so the Garage keeps about 1.5 h (LG:42). The other choice is a shorter Garage | the sims (`--long`, S10) | 3 |
| 3 | Placeholder Garage prices: Coffee Machine $150, Laptop $800, first egg $400, Desk 2 $1,000, new Desk 3 $2,500, Bug Beetle egg $3,000 | `LONG_ITEMS`, then TycoonCore UPGRADES and CreatureConfig in LONG PR 2 | 3 |
| 4 | Garage milestones at $5K / $20K / $60K / $120K valuation, giving a title, decor, a task preview, decor (no Cash) | the sims; a config list | 3, 4 |
| 6 | The goal chain and its texts: "Answer 3 calls", "Own 3 upgrades", "Hire 3 employees", "Reach milestone 1", "Get a x2 chain", "Buy the Server Rack", milestones 2-4, "Reach Seed" (shipped keys `Hire3` and `Seed` kept) | `OnboardingConfig.Goals` plus new goal kinds | 4 |
| 7 | A "Cheer" on a neighbor's sign as the first social moment (a clap, no reward, rate-limited); poaching stays closed in the first hour | a new small feature, or drop it | 4 |
| 5 | Tutorial order: TUT 1 Desk, **TUT 5 on the first ring**, TUT 2 hatch, TUT 4, TUT 3 as "one hire per desk", **TUT 6 after the third hire (~12:20)** | `TutorialConfig` (TUT PR A) | 3 |

## Not verified

- Whether Roblox's player list (the only place Cash and Income show today) is visible by default on phones (finding A1).
- Everything about real players: the model's delays are guesses until the 5-friend playtest (section 9).
