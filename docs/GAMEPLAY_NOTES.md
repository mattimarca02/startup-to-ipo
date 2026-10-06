# Gameplay first hour: working notes

Notes for `docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md` (branch `gameplay-design`, worktree `../gameplay-design`, started 2026-10-06). Docs only: no code, no Studio, no MCP. The only existing-file edit is the two claim rows in `CONTRIBUTING.md`.

## Progress (session 2: owner decisions, 2026-10-06)

Worktree `../gameplay-fold` from `origin/gameplay-design` (e48dfc0), branch `gameplay-fold`, each commit pushed to `gameplay-design` (fast-forward). Docs and one new tool; no Studio, no MCP; `tools/economy_sim.py` and `docs/SIMS_RESULTS.md` only read.

- [x] Claim the two docs and the new `docs/SOUND_PLAN.md`, `tools/first_hour_model.py` (99ca4c1)
- [x] Item 1 (5345cb3): D1-D8 recorded as DECIDED BY THE OWNER, open questions replaced (8 left), build order re-tagged (the bar is 1, `SoundConfig` 5, assets 15); 5,490 words (the numbers come from the item 2 model, committed next)
- [x] Item 2: `tools/first_hour_model.py` (standard library, deterministic, 0.1 s; `--check` compares the 8 doc blocks and 17 copied constants with their sources; `--previous` prints model G); doc numbers from it
- [ ] Item 3: `docs/SOUND_PLAN.md` (at most 2,000 words)
- [ ] Item 4: 15+ citations checked against `origin/main` (and `origin/task-needs-desk`), word counts
- [ ] Release the four claims

## Progress (session 1)

- [x] Worktree `../gameplay-design` from `origin/main` (e3c9e67), branch `gameplay-design`
- [x] Claim both docs in `CONTRIBUTING.md` (9f54c8d, pushed)
- [x] Read the docs and scripts listed in the brief (all found; see Sources)
- [x] Run `python tools/economy_sim.py` (default output, read-only; 5.5 s, exit 0)
- [x] Section 1: Audit
- [x] Section 2: The core loop
- [x] Section 3: The first 10 minutes
- [x] Section 4: The first hour
- [x] Section 5: Game feel
- [x] Section 6: Monetization that feels fair
- [x] Section 7: Frustration and safety nets
- [x] Section 8: Sectors
- [x] Section 9: Measurement
- [x] Section 10: What to build, in order
- [x] Section 11: Open questions
- [x] Word count at most 5,500 (`wc -w`): 5,445 after section 11, 5,466 after the review pass
- [x] Release both claims in `CONTRIBUTING.md` (rows kept, set to free)

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
5. **A third Garage desk.** A first draft with cheaper first items only still left a 10-minute wait from 8:00 to the Server Rack. Adding Desk 3 brings the longest wait in minutes 0-20 to about 6 minutes, and it also fixes the free-egg conflict (the free hire takes Desk 1 in LONG's list, which assumes the first hire is bought). A second draft priced a separate $3,000 Bug Beetle egg; I dropped it because LONG has one egg price per tier (LG:42) and the desks are what gate hires, so Desk 3 carries the price ($5,000) and every Garage Egg costs $400. The proposal's "model G" is this final version (scratch file `g3_model.py`): Desk 0:30, first call 0:53, hire 1:22, Coffee Machine 1:43, Laptop 3:34, Desk 2 4:51, egg 5:21, hire 6:41, milestone 1 8:02, Desk 3 10:25, egg 10:54, hire 12:14, milestone 2 18:27, Server Rack 19:00, Whiteboard 28:37, milestones 3-4 30:05 and 39:13.
6. **No computer rival for solo players.** A Studio dummy exists (PoachServer.lua:776-792), but a live one that can be poached would hand out free employees and bypass LG's R2 (3 poach-ins per run). Solo players get everything else and a clear "when poaching opens" line instead.
7. **The Day 1 gift goes after minute 10, not at 7:00.** At 7:00 the $4,200 gift would buy Desk 3 and an egg at once and leave a long wait after it; after the third hire (~12:15) its ~$6,600 shortens the longest wait (12:14 to 19:00) instead.
8. **Findings about today that LONG PR 2 fixes** (A4, A5, A20) are kept in the list, marked "(today)" and "planned", so the owner sees what a launch on today's code would feel like.

## Judgment calls (session 2)

9. **Where D1's numbers changed.** The new model gives every Garage Egg hire the egg's average ($4.97/s, today's odds) instead of model G's fixed 3 / 3 / 8 (a $400 egg cannot promise a Bug Beetle), adds the Day 1 gift after the third hire, and stops flooring call pay. So Desk 3 comes at 8:32 instead of 10:25 and the Server Rack at 13:00 instead of 19:00.
10. **Keeping the Garage at 1.5 h.** With D1 prices and LONG_K unchanged, Seed comes at 37:02. The model raises the Whiteboard and Neon Logo by the smallest factor that brings Seed back to 1:30 (x3.1), only so D2's milestones have amounts. That leaves a 17-minute wait after the Server Rack, so it is open question 1, not a proposal; `economy_sim.py --long` owns the re-fit.
11. **D2 shares.** The Garage uses 1 / 12 / 30 / 50% (milestone 1 before 10:00, the others inside the late waits); every other rung keeps LONG 4(b)'s 20 / 40 / 60 / 80%. Series C+D keeps LG 4(b)'s decor and task tier besides the title and star. Entry titles stay the content bible's, so "Garage Dreamer" is no longer milestone 1's title (it was in session 1's draft).
12. **D6 reference Income.** A tier's price per Income = its egg price ÷ the Income of the hire LONG prices that egg at (LG:38: "egg price = the rung's first hire"), because the five later tiers have no odds yet. For the Garage that is the Coding Cat (3/s), not the egg's $4.97/s average.
13. **D3's "later"** is read as the second founding (session 1's default, CUST 1.3's greyed cards).
14. **D5 table** uses D6 prices and base chances; the Recruiter Network perk (IpoConfig.lua:104-106) is left at level 0.
15. **Word budget.** `wc -w` counts table pipes and spaced separators, so tables became lists where a table carried no comparison, and every dropped sentence was a repeat. Session 1's numbers and citations were kept: its minute-by-minute table of today became one model line (reproduced exactly), and the session's "1.3 findings" are now 1.2.

## The model (session 2)

`tools/first_hour_model.py` replaces session 1's scratch files (`first_hour_model.py` with models A-H, `g3_model.py` = model G), which survived in that session's scratch folder and were read, not copied. Two engines: a fixed buying order for the launch Garage, and a line-by-line port of the old greedy model for the "Today" and "Launch as planned" columns.

**Reproduced exactly:** model A (today, live: every pacing time and the Cash / Income line, $398 / $13 at 2:00 ... $67,672 / $208 at 10:00; the old model truncated Cash, so the line does too), model B (Studio calls: first call 0:53, Seed 2:30, Garage done 3:48, IPO-ready 8:40), model D (launch as planned: call 0:53, hire 1:22, Coffee Machine 5:01, Desk 2 13:20, egg 18:11, hire 19:31, Laptop 25:04, longest wait 8:19) and model G (`--previous`: all 16 events, 0:30 to 39:13). **Not re-run:** models C, E, F, H; the doc keeps one number from E (the Coffee Machine at ~16:00 without the free egg) and says so.

**What changed in D1's numbers against model G** (G = session 1's proposal):

| | Model G | D1 now | Why |
|---|---|---|---|
| Coffee Machine, Laptop | 1:43, 3:34 | 1:36, 3:00 | the free hire is worth $4.97/s, not $3 |
| Desk 2, egg, hire 2 | 4:51, 5:21, 6:41 | 4:04, 4:27, 5:47 | same |
| Milestone 1 | 8:02 ($5,000) | 6:47 ($4,900) | D2's 1% of a $492K Garage |
| Desk 3, egg, hire 3 | 10:25, 10:54, 12:14 | 8:32, 8:48, 10:08 | Incomes as above |
| Day 1 gift | not modelled | 10:18, +$6,870 | added (TUT 6) |
| Server Rack | 19:00 | 13:00 | the gift |
| Longest wait 0-20 min | 6:13 | 2:52 | all of the above |
| Whiteboard, Neon Logo | 28:37 ($28K), not bought | 41:02 ($87K), 1:18:59 ($220K) | the x3.1 Garage fit (judgment call 10) |
| Milestones 2-4 | 18:27, 30:05, 39:13 | 27:55, 49:43, 1:06:54 | D2 amounts on the fitted Garage |
| Longest wait 20 min to Seed | not measured | 17:11 | new row |
| Seed | ~90 min (assumed) | 1:30:04 (37:02 unfitted) | measured |

## OWNER CHOICE

Defaults picked where the owner's taste decides. Rows 1, 3, 4, 8, 13 and 15 were settled by the owner on 2026-10-06 (D1-D4, D8: see the proposal's section 0); row 2 is now open question 1. Rows 16-19 are session 2's.

| # | Default picked | Where it is decided later | Section |
|---|---|---|---|
| 1 | DECIDED (D3). The very first founding shows the sector picker (D-C) with **Software preselected**, because both sectors are "not done" for a new player (CUST 1.3) and Software teaches the shared engine | `SectorConfig` / the picker (CUST PR 4) | 3, 8 |
| 2 | NOW OPEN QUESTION 1. The cheaper first Garage items are paid back by raising the **Whiteboard and Neon Logo**, so the Garage keeps about 1.5 h (LG:42). The other choice is a shorter Garage | the sims (`--long`, S10) | 3 |
| 3 | DECIDED (D1). Placeholder Garage prices: Coffee Machine $150, Laptop $800, the Garage Egg $400 (one price per tier, LG:42), Desk 2 $1,000, a new Desk 3 $5,000 | `LONG_ITEMS`, then TycoonCore UPGRADES and CreatureConfig in LONG PR 2 | 3 |
| 4 | DECIDED (D2), amounts replaced: milestones in every rung, a title and a star each (proposal 3.4) | the sims; a config list | 3, 4 |
| 5 | Tutorial order: TUT 1 Desk, **TUT 5 on the first ring**, TUT 2 hatch, TUT 4, TUT 3 as "one hire per desk", **TUT 6 after the third hire (~12:15)** | `TutorialConfig` (TUT PR A) | 3 |
| 6 | The goal chain and its texts: "Answer 3 calls", "Own 3 upgrades", "Hire 3 employees", "Reach milestone 1", "Get a x2 chain", "Buy the Server Rack", milestones 2-4, "Reach Seed" (shipped keys `Hire3` and `Seed` kept) | `OnboardingConfig.Goals` plus new goal kinds | 4 |
| 7 | A "Cheer" on a neighbor's sign as the first social moment (a clap, no reward, rate-limited); poaching stays closed in the first hour | a new small feature, or drop it | 4 |
| 8 | REPLACED (D8: sound at launch). **Silent by default.** Sounds only from Roblox-made Creator Store assets the owner picks, in a `SoundConfig` with `id = 0` placeholders; volume 0.5; a "Sounds" toggle | `SoundConfig` | 5 |
| 9 | Employee states Work / Stroll / React / Rest ("Zz" in quiet mode), and Coffee Capybara's coffee breaks | EmployeeClient | 5 |
| 10 | Effect budgets: walkers 20 Hz within 80 studs and on screen; 6 floating texts; one burst of 30 particles; tweens 0.6 s or less | the juice PRs | 5 |
| 11 | **No starter offer and no unprompted Robux surface:** the first Robux prompt is the player's own tap on a price in SHOP; no badge points at a Robux tab | ShopClient (SHOP_UX S4) | 6 |
| 12 | At launch the Extra Employee Slots pass means **+3 desks**, capped like every desk (LG:60 estimates up to +15% Income) | LONG PR 3 (desks) | 6 |
| 13 | DECIDED (D3). A first founding **hides the Fintech and Biotech "Coming soon" cards** (CUST 1.3 shows them greyed); they appear from the second founding. Picker texts: Software "Answer customers, grow steady", Gaming "Make games, launch hits" | the picker (CUST PR 4) | 8 |
| 14 | Funnel targets (95 / 85 / 85 / 60 / 50 / 25% ..., day 1 ≥ 25%, day 7 ≥ 8%, first IPO 3% by day 30) are placeholders to replace after the first 100 players | the analytics PR | 9 |
| 15 | DECIDED (D4). **Cash and +$/s go on the valuation bar's top line**; the stage name moves to its second line (no new HUD element: the top row and the left column are full) | IpoClient (build order 1) | 1, 10 |
| 16 | Headhunter's fixed effect: **A, 20% off every poach** (stacks with Recruiter Network) | the owner (D5) | 6.1 |
| 17 | D2 milestone shares (Garage 1 / 12 / 30 / 50%, others 20 / 40 / 60 / 80%) and the 24 titles | `IpoConfig` or a title list (build item 10) | 3.4 |
| 18 | D6 rule: Income x the home tier's egg price per Income, floor at the egg price, 2 significant digits | `CreatureConfig.Poaching` (build item 14) | 6.2 |
| 19 | Music off by default, effects on | `SoundConfig` | 5, SOUND |

## Not verified

- Whether Roblox's player list (the only place Cash and Income show today) is visible by default on phones (finding A1).
- Everything about real players: the model's delays are guesses until the 5-friend playtest (section 9).
- Roblox audio: the Creator Store license terms for Roblox-made sounds, the current upload allowance and fees, and which assets the 2022 audio privacy rules let any experience play (section 5).
- An API that tells a script the player's graphics quality, to drop particles on low settings (section 5).
- Creator Hub's built-in analytics (which charts exist today) and `AnalyticsService` method names: written from memory, no dashboard or docs opened (section 9).
- Streaming the plot in before the teleport (WORLD §3 marks it unverified too); how a phone behaves when the plot arrives late (section 7).
- Launch-build poaching economics (A13): LONG prices against today's poach cost rule, not simulated (SIMS §7 lists poaching as not modeled).
- The time a new player spends on the sector picker and on reading tutorial cards: the model starts the Desk at 0:30 and ignores reading time.
- No Studio, no MCP and no playtest were used; `tools/daily_test.py` was not run (docs only). Gaming numbers are SECT's placeholders, read, not re-run.

## Results

- Proposal: `docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md`, 11 sections, 5,466 words (`wc -w`), 20 audit findings, 18 build items, 8 open questions.
- Commits (each pushed right after): 9f54c8d claim, 243e2ae notes, db8b721 section 1, 289bde8 section 2, c314c0b section 3, 6111003 section 4, 3412bb9 section 5, c667ada section 6, 669fd5a section 7, 59db7c8 section 8, 097856c section 9, 4e5f9a5 section 10, b047237 section 11, 66b8c95 review pass, then the claim release.
- Scratch files (outside the repo, not committed): the sim's default output, `first_hour_model.py` (models A-H), `g3_model.py` (the proposal's model G).
- Every explicit `file:line` citation in the proposal was printed against the file and checked once more at the end.
