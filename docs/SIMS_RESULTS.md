# Sims S1-S10: results (design-doc sims, run before any build)

Run 2026-10-05, branch `sims-two-sectors-clean` (see the branch note in section 6), script `tools/economy_sim.py` (new code only; no `.lua` file, no `tools/daily_test.py`, no design doc touched). Numbers come from `python tools/economy_sim.py <flag>` (each sim has its own flag, default OFF; `--runs N` sets the seeds, default 40). Every number in the three design docs is a **placeholder**; this file measures them, says PASS / FAIL / marginal against the mark the doc gives, and for each FAIL or marginal result gives the smallest change to the placeholder and the re-run with it.

`CUST` = docs/CUSTOMIZE_PROPOSAL.md, `FUND` = docs/FUNDING_ROUNDS_PROPOSAL.md, `SECT` = docs/SECTORS_PROPOSAL.md, `LG` = docs/LONG_GAME_PROPOSAL.md; `CUST:122` = that file, line 122, as on `main` `e3c9e67`.


## 1. The sims the docs name

Searched all of `docs/` on `main`. Ten sims are named, S1-S10; no other numbered sim exists. The list is what each must measure, the mark the doc gives, and the line that says so.

| Sim | Flag | Must measure | Mark (from the doc) | Doc lines |
|---|---|---|---|---|
| **S1 seed** | `--s1` | Seed Cash at a founding (s% of the old company's Cash, capped at c% of the new first rung's prices): 0 / 10 / 25% cap | each loop at most 5% faster than with no seed; a "decorator" (puts its Cash into furniture, so no seed) at most 5% slower | CUST:122, rule CUST:115, "seed Studio only until S1" CUST:148, gate G-S (c) CUST:154 |
| **S2 bonus** | `--s2` | Collection bonus, 0-12 points, times the pass sets (Cash, VIP, Shareholder); the +10% cap with the Shareholder and Cash passes | at the cap, at least 95% of the no-bonus hours; never valuation | CUST:122, rule CUST:117, PR 12 needs it CUST:164 |
| **S3 parity** | `--s3` (also in `--gaming`) | Software against Gaming (typical launch policy), hours per engaged hour, every rung and every `LONG_PLAYERS` profile; fits Gaming's upgrade Incomes | within +-5% | CUST:122, CUST:87, SECT:157, SECT:55; gates CUST:154 (c) and CUST:159 (a); one `HoursShare` table needs it FUND:109, FUND:128 |
| **S4 bots** | `--s4` | A task-bot (and a macro, and a pulse-bot) in each sector | no sector faster for a bot | CUST:122, SECT:158, PR 12 CUST:164 |
| **S5 hopping** | `--s5` | Alternating Software and Gaming against staying in one, 10 IPOs | under 3% | CUST:122, SECT:158, gate CUST:154 (c) |
| **S6 tiers** | `--s6` | Stamp tiers from (time, ratio, stake): Gold 1.0 T + stake 55%, Platinum 0.8 T + ratio 1.25 + stake 70%; pass owners with the pass-share targets | Gold on at least 50% of regular replays; Platinum on at least 20% of dedicated ones; pass owners within +-5 points | CUST:122, rules CUST:69-70, open question CUST:191, PR 12 CUST:164 |
| **S7 board** | `--s7` | Leaderboard: a new sector against replays; the task-bot against a dedicated human | within 10%; the bot never above the human | CUST:122, PR 13 CUST:165 |
| **S8 round size** | `--s8` (`--rounds`) | Funding rounds, policies none / Small / Medium / Large-every-round / best-per-stage, per profile, loops 1-10: hours per IPO, Shares, perk timing; is the maximum always best; which curve makes the choice real; hours saved against Shares lost; **speed against stamp tier lost on stake, for a player whose Shares are worth nothing**; for Software **and** Gaming; today's 5 stages and LONG_GAME's 7 | no one choice best for every profile; Large-every-round saves at most 15% of a loop; the stake minimum prices Large-every-round without taking Platinum from most runs; cap and minimums not redundant; converter and alt-fed gain under 3% in loop 2; raising the last open round never beats skipping it; the same round saves hours within 5% in the two sectors; no choice dominated at any stage | CUST:123, FUND:105-111 (marks FUND:107, both sectors FUND:108, Gaming FUND:109, needs FUND:111), FUND:58, 82, 89-91, SECT:161, CUST:149, gate CUST:154 (c) |
| **S9 launch policy** | `--s9` (also in `--gaming`) | Gaming's five launch policies (Smash, Hit, Solid, Flop, never ship) per profile; launch-spam; update timing | Smash at most 5% faster than Software; Solid at most 12% slower; Flop at most 25% slower; launch-spam gains at most 1%; best against worst update timing at most 5% | SECT:159, policy table SECT:133-141, CUST:122, gate CUST:159 (a) |
| **S10 cadence** | `--s10` (also in `--gaming`) | Moments per hour per rung for both sectors (LG:66-79) | no gap over 45 engaged minutes; Gaming's longest wait between decisions under 15 minutes | SECT:160, gate CUST:159 (a) |

Checks the docs ask for inside these sims, all covered below: round Cash is a gift and never feeds the valuation (FUND:5, 20, 25; the engine asserts it on every raise); the funding table in whole basis points recomputed from the formula (FUND:38); the 1,024 round sequences and who loses Platinum (FUND:81); engaged-time rules, 3 h a day at full value then 5%, day boundary 08:00 UTC (SECT:85, LG:23); launch-spam and the 4th update lifting less (SECT:122-123).

## 2. How the sims are built

- **Engine.** `pk_run` in `tools/economy_sim.py` is a copy of `long_run` (the `--long` model: the 97-item ladder, the engaged clock, the 3 h/day rule, the away bank, loop growth, Shares and one speed perk) with hooks for a sector per loop, seed Cash, the Collection bonus, funding rounds with dilution, stamp tiers and the hunt for Platinum. **With every hook off it reproduces `long_run` exactly** (same hours, Shares, stage times and days, checked on 24 runs x 3 loops every time a sim runs: the line "Engine check" at the top of each output). Nothing above the new block was edited, so `python tools/economy_sim.py` and `--long` print the same bytes as before (diffs in section 6).
- **Same random numbers.** Seed `s` of a profile draws the same stream whatever the option, so two options differ only by what they change; the tables give the per-seed change as median (p10 to p90), never one run.
- **Profiles.** Schedules: `dedicated` (2 h a day), `regular` (1 h), `casual` (3 h a week), the `task-bot`, `pulse-bot`, `macro` and `reference` of `--long`, plus `heavy` (5 h a day) and `boundary` (a session across 08:00 UTC) added here to exercise the 3 h cap and the day boundary. Skills: `typical` (the default), **fast** = `expert` at tasks, **slow** = the task bonus x0.5 (LG:6's own sensitivity row). Passes: none, VIP (x1.5 Cash), 2x Cash, Cash + VIP (x3), Shareholder (x2 Shares), Cash + Shareholder.
- **Valuation is base Cash** (LG:93), and a pass, the bonus, the seed and a round change spendable Cash only.


## 3. Results

(Summary table of all ten sims: section 0 above; the placeholder numbers that must change: section 4 below.)

### S1. Seed: PASS

**Finding.** The seed is worth about **1.2% of a loop** (+1.14% to +1.38% over the variants, at most +1.5% at p90): it makes the Garage rung of the next company about 60% faster, but the Garage is 1.5 of 57 hours. The mark is 5%, so the placeholder 10% / 25% is far inside it. A decorator who ends with no Cash loses that 1.2% (mark 5%: PASS). Only the extreme "heavy decorator" assumption (10% of *all* Cash into furniture) reaches 4.0%, close to the mark but a choice, not a loss of the seed.

**Two things the doc did not expect.** (1) The "s%" half of the rule never binds: the old company ends the first run with a median of 785M Cash (every item is bought long before the IPO threshold, which is 1.5 x the price of everything), against a cap of 52K, so `s` would have to be under 0.007% to matter. The seed is only "c% of the new first rung's prices". (2) Because of that, any `s` from 1% up gives the same result; keep `s` for readability or drop it.

**Assumptions.** "The new first rung's prices" = the sum of the Garage rung's item prices at the new loop's StageScale (131K x StageScale); the alternative reading, c% of the valuation that opens Seed, gives +1.3%. A decorator = no leftover Cash at the IPO. Furniture prices are not in the doc, so "heavy decorator" (10% of all Cash) is my number.

## S1. Seed Cash at a founding (docs/CUSTOMIZE_PROPOSAL.md 5.1, 5.5)
Software ladder (LONG_ITEMS), typical skill, no rounds, no passes, 40 seeds per cell, 4 loops. Seed = min(s% of the old company's Cash, c% of the new first rung's prices x StageScale), a gift: Cash only, never valuation (the engine adds it to `cash` and asserts nothing else moves). Numbers are the change of that loop's engaged hours against the same seed with no seed (positive = faster), median (p10 to p90) over seeds.

**regular** (loop 0 is the first company: no seed, so no change)

| Variant | Loop 1 (IPO 2) | Loop 2 (IPO 3) | Loop 3 (IPO 4) | Garage rung of loop 1 |
|---|---|---|---|---|
| s 10%, cap 10% | +0.91% (+0.78% to +1.00%) | +0.91% (+0.68% to +1.04%) | +0.94% (+0.77% to +1.02%) | +50.8% (+47.5% to +56.8%) |
| **s 10%, cap 25% (the doc's placeholder)** | +1.14% (+1.01% to +1.24%) | +1.17% (+0.89% to +1.28%) | +1.13% (+0.97% to +1.28%) | +63.0% (+60.3% to +64.8%) |
| s 10%, cap 50% | +1.35% (+1.16% to +1.44%) | +1.38% (+1.09% to +1.46%) | +1.33% (+1.14% to +1.50%) | +71.7% (+69.8% to +73.4%) |
| s 100%, cap 25% (only the cap limits) | +1.14% (+1.01% to +1.24%) | +1.17% (+0.89% to +1.28%) | +1.13% (+0.97% to +1.28%) | +63.0% (+60.3% to +64.8%) |
| s 10%, cap 25% of the next threshold (other reading of 'first rung's prices') | +1.28% (+1.12% to +1.36%) | +1.32% (+1.05% to +1.42%) | +1.26% (+1.09% to +1.42%) | +69.2% (+68.0% to +71.1%) |
| decorator: spent every leftover Cash on furniture (seed 0); compared with the 10% / 25% player | -1.15% (-1.26% to -1.02%) | -1.19% (-1.30% to -0.90%) | -1.15% (-1.29% to -0.98%) | -170.4% (-184.2% to -152.2%) |
| heavy decorator: also puts 10% of all Cash into furniture, no seed; compared with the 10% / 25% player (ASSUMPTION: 10%) | -3.96% (-4.08% to -3.71%) | -3.93% (-4.14% to -3.67%) | -4.00% (-4.12% to -3.71%) | -188.3% (-256.3% to -152.0%) |

Old company's Cash at the first IPO: median 782.33M; the cap (25% of the Garage rung's prices at loop 1) is 51.74K; the seed paid: median 51.74K. So the cap binds in 100% of runs and 's' never does.

**dedicated** (loop 0 is the first company: no seed, so no change)

| Variant | Loop 1 (IPO 2) | Loop 2 (IPO 3) | Loop 3 (IPO 4) | Garage rung of loop 1 |
|---|---|---|---|---|
| s 10%, cap 10% | +0.93% (+0.75% to +1.00%) | +0.88% (+0.69% to +1.06%) | +0.93% (+0.67% to +1.02%) | +50.7% (+48.0% to +53.5%) |
| **s 10%, cap 25% (the doc's placeholder)** | +1.14% (+0.96% to +1.22%) | +1.10% (+0.92% to +1.26%) | +1.15% (+0.97% to +1.26%) | +62.5% (+60.5% to +64.7%) |
| s 10%, cap 50% | +1.33% (+1.17% to +1.40%) | +1.35% (+1.16% to +1.46%) | +1.35% (+1.17% to +1.47%) | +71.8% (+70.5% to +74.1%) |
| s 100%, cap 25% (only the cap limits) | +1.14% (+0.96% to +1.22%) | +1.10% (+0.92% to +1.26%) | +1.15% (+0.97% to +1.26%) | +62.5% (+60.5% to +64.7%) |
| s 10%, cap 25% of the next threshold (other reading of 'first rung's prices') | +1.28% (+1.09% to +1.34%) | +1.29% (+1.04% to +1.38%) | +1.30% (+1.12% to +1.44%) | +69.0% (+67.9% to +71.4%) |
| decorator: spent every leftover Cash on furniture (seed 0); compared with the 10% / 25% player | -1.15% (-1.24% to -0.97%) | -1.11% (-1.28% to -0.93%) | -1.17% (-1.27% to -0.98%) | -167.0% (-183.7% to -153.2%) |
| heavy decorator: also puts 10% of all Cash into furniture, no seed; compared with the 10% / 25% player (ASSUMPTION: 10%) | -3.91% (-4.04% to -3.70%) | -3.92% (-4.08% to -3.68%) | -3.93% (-4.12% to -3.73%) | -187.2% (-242.4% to -148.3%) |

Old company's Cash at the first IPO: median 783.24M; the cap (25% of the Garage rung's prices at loop 1) is 51.74K; the seed paid: median 51.74K. So the cap binds in 100% of runs and 's' never does.

**Result.** Placeholder (10% / 25%): the best loop is +1.17% faster (median), against the mark of 5%: PASS. The decorator (seed 0) is at most 1.19% slower than the seeded player: PASS; a heavy decorator (10% of all Cash in furniture) 4.00% slower (PASS, but only because the 10% is a choice).

### S2. Collection bonus: PASS

**Finding.** At the cap (+10 points of Cash) the run takes **96.6%** of the no-bonus hours for a player with no pass (3.4% faster), **99.0%** with the 2x Cash pass and **99.7%** with 2x Cash + VIP; the bonus helps pass owners less because they already buy everything sooner. At 12 points the cap holds (same numbers as 10). Mark: 95% or more at the cap: PASS for every pass set. The Shareholder pass is unaffected (the bonus is Cash only: 40 Shares at IPO 1 with and without it). Stacked, 2x Cash x VIP x 1.10 = x3.3 of spendable Cash, and still under 1% of speed for that player.

**Why so small.** A Cash multiplier only moves the moment items are bought; rungs open on valuation, which counts base Cash. This is also why the cap could be higher: a +25% cap would still be 8% for a no-pass player. No change proposed (not needed).

**Assumptions.** The bonus multiplies spendable Cash in the same place as the passes (`updateIncome`, CUST 5.2), so task Cash and away pay are multiplied too; valuation untouched. Tested on Software only, because the bonus does not depend on the sector.

## S2. Collection bonus x passes (docs/CUSTOMIZE_PROPOSAL.md 5.2, 5.5)
Software ladder, regular player, typical skill, 40 seeds, IPO 1 and IPO 2. The bonus is a Cash multiplier of (1 + points/100) on top of the passes (2 x 1.5 x 1.10 = x3.3), applied to spendable Cash only: the valuation counts base Cash (LONG_GAME section 6), so the bonus never reaches it. 'Points' above the cap (10) count 10. Cell = engaged hours of that IPO as a % of the same pass set with 0 points, median (p10 to p90); the mark is 95% or more at the cap.
| Pass set | Cash x | 1.5 pts | 3 pts | 5 pts | 7.5 pts | 10 pts | 12 pts (cap 10) |
|---|---|---|---|---|---|---|---|
| none | x1 (x1.10 at the cap) | 99.4% (99.4 to 99.5); loop 2 99.7% | 98.9% (98.8 to 99.0); loop 2 99.3% | 98.2% (98.1 to 98.3); loop 2 98.9% | 97.4% (97.3 to 97.5); loop 2 98.4% | 96.6% (96.6 to 96.7); loop 2 97.9% | 96.6% (96.6 to 96.7); loop 2 97.9% |
| VIP | x1.5 (x1.65 at the cap) | 99.7% (99.7 to 99.7); loop 2 99.9% | 99.4% (99.4 to 99.5); loop 2 99.7% | 99.1% (99.0 to 99.2); loop 2 99.5% | 98.7% (98.6 to 98.8); loop 2 99.3% | 98.3% (98.2 to 98.4); loop 2 99.1% | 98.3% (98.2 to 98.4); loop 2 99.1% |
| Cash | x2 (x2.20 at the cap) | 99.8% (99.8 to 99.9); loop 2 99.9% | 99.7% (99.6 to 99.7); loop 2 99.9% | 99.5% (99.4 to 99.5); loop 2 99.8% | 99.2% (99.2 to 99.3); loop 2 99.7% | 99.0% (99.0 to 99.0); loop 2 99.5% | 99.0% (99.0 to 99.0); loop 2 99.5% |
| Cash+VIP | x3 (x3.30 at the cap) | 99.9% (99.9 to 100.0); loop 2 100.0% | 99.9% (99.9 to 99.9); loop 2 100.0% | 99.8% (99.8 to 99.9); loop 2 100.0% | 99.7% (99.7 to 99.8); loop 2 99.9% | 99.7% (99.6 to 99.7); loop 2 99.9% | 99.7% (99.6 to 99.7); loop 2 99.9% |
| Shareholder | x1 (x1.10 at the cap) | 99.4% (99.4 to 99.5); loop 2 99.7% | 98.9% (98.8 to 99.0); loop 2 99.3% | 98.2% (98.1 to 98.3); loop 2 98.9% | 97.4% (97.3 to 97.5); loop 2 98.4% | 96.6% (96.6 to 96.7); loop 2 97.9% | 96.6% (96.6 to 96.7); loop 2 97.9% |
| Cash+Shareholder | x2 (x2.20 at the cap) | 99.8% (99.8 to 99.9); loop 2 99.9% | 99.7% (99.6 to 99.7); loop 2 99.9% | 99.5% (99.4 to 99.5); loop 2 99.7% | 99.2% (99.2 to 99.3); loop 2 99.6% | 99.0% (99.0 to 99.0); loop 2 99.5% | 99.0% (99.0 to 99.0); loop 2 99.5% |

(Shareholder: Shares at IPO 1 with the bonus at the cap 40, without 40)

(Cash+Shareholder: Shares at IPO 1 with the bonus at the cap 40, without 40)

**Result.** At the cap the shortest run is 96.6% of the no-bonus hours (mark: 95% or more): PASS. Shares are unchanged by the bonus (it never reaches the valuation).


### S3. Parity of the two sectors: FAIL as written, marginal after two changes

**Finding.** The Gaming title cycle of SECTORS 2.2-2.4 (Hit policy, doc numbers) can be fitted so that Software and Gaming take the same hours in every rung for the reference player, and then **every schedule at the typical skill stays within +-3.0%** (dedicated, regular, casual, boundary: 0.2% to 3.0%, the worst being the Garage rung of the dedicated player; `heavy` 4.8% in one noisy rung; IPO 2 and 3 within 0.2%). That is the doc's rule and it passes. It fails in three places:

1. **The fit is skill-dependent.** The extra is a fixed share of base Income, but the task bonus is not, so a slow player (task bonus x0.5) gets 5-6% *more* out of Gaming and a fast one (expert at tasks) 2-6% *less* (Garage rung). Slow players are 6.3% faster in Gaming at Pre-IPO, outside the mark; fast players are 5.6-5.8% slower in the Garage rung.
2. **Away-heavy players.** The away bank pays 10% of base Income and the extra is never in it (SECTORS 2.4), and Gaming's base is lower, so a check-in player (1 minute a day) is 26-28% slower in Gaming in the Garage rung. This profile never reaches the IPO, but it is in `LONG_PLAYERS`, so it is a FAIL against "every profile".
3. `heavy` (5 h a day) with the slow skill is noisy: the 3 h/day rule quantises when a rung is crossed.

**The doc's 0.77.** Gaming's *total* base Income measured at the end of each rung is 0.74-0.83 of Software's, so the doc's fitted base 0.77 is right as a total. The fitted *upgrade* factor is lower, **0.72 / 0.66 / 0.65 / 0.59 / 0.61 / 0.41** for Garage ... Pre-IPO, because hires keep CreatureConfig's Income and carry more of the total late. The measured average extra is 0.35 in the Garage and 0.50-0.52 in every later rung (the doc's table averages 0.30 for the Hit policy), and the cycle launches **49 titles** to IPO 1 (the doc estimates about 40: 4 / 5 / 6 / 6 / 14 / 7; measured 4 / 7 / 8 / 7 / 14 / 9).

**Smallest changes, re-run (outputs below).**
- *Fix A, away bank:* Gaming's away bank pays on the base Income the same purchases would give in Software (one data field in `SectorGaming`, no new call site). Check-in goes from +26% to +12% in the Garage rung and 98-102% in the other rungs it reaches; casual stays at 99-101%.
- *Fix B, smaller launch revenue:* peaks x0.6 (0.09 / 0.21 / 0.36 / 0.48), cap 0.48, back catalog cap 0.06, then refit: the upgrade factor becomes **0.81 / 0.78 / 0.78 / 0.73 / 0.75 / 0.61**, the skill spread halves (slow 96.0%, fast 100.5-103.8%) and every schedule at every skill is inside +-5% except the Garage rung of check-in (+7%; that rung is 20 minutes of engaged play), and `heavy/slow` (5.9%, one noisy cell). Cost: launch tiers matter less (S9 re-run with fix B is in its section).

**Assumptions.** Everything the doc leaves open: scope factor 1.0 for every scope ("same x scope"); Fun and Polish are not simulated separately, a polish curve through Score 55 at content complete, 70 at 0.5 x the work, 90 at 1.5 x (the doc gives only the first); trend and trailer always achieved; Gaming's task bonus = Software's (the engine's budget is the ceiling for both); an update is a free verb after a 10-minute cooldown, lifting revenue to 70 / 60 / 50 / 40 ... % of the peak; the typical policy updates when revenue is under half the peak. Full list in section 5.

## S3. Parity: Software and Gaming, hours per engaged hour (docs/SECTORS_PROPOSAL.md 2.4, 4; docs/CUSTOMIZE_PROPOSAL.md 5.5)
Gaming model: the title cycle of SECTORS 2.2-2.4 (scope per rung, peak x tier, half-life, Live Updates, back catalog, cap 0.8), typical policy = Polish to Hit with an update when revenue is under half the peak; its extra pays x base Income on top of the base and the task bonus, only while engaged, never in the away bank. Gaming's upgrade Incomes are scaled by beta per rung (hires keep CreatureConfig's Income), fitted rung by rung with the always-engaged reference player (typical skill) so that each rung takes the same hours as in Software. Assumptions: section 'Assumptions' of docs/SIMS_RESULTS.md.

### Fit 1: the doc's rule (fit to the typical player)
| Rung | Software h | Gaming h, beta 1.0 (no fit) | fitted beta | Gaming h after the fit | Gaming base Income / Software's at the end of the rung | average extra (x base) | titles launched in the rung |
|---|---|---|---|---|---|---|---|
| Garage | 1.50 | 1.20 | 0.721 | 1.50 | 0.74 | 0.35 | 4 |
| Seed | 3.98 | 2.96 | 0.661 | 3.98 | 0.75 | 0.52 | 7 |
| Series A | 6.51 | 4.98 | 0.655 | 6.51 | 0.81 | 0.52 | 8 |
| Series B | 9.02 | 7.08 | 0.585 | 9.02 | 0.81 | 0.51 | 7 |
| Series C+D | 23.84 | 19.21 | 0.607 | 23.84 | 0.83 | 0.50 | 14 |
| Pre-IPO | 15.01 | 12.14 | 0.405 | 15.02 | 0.82 | 0.50 | 9 |

Total titles to IPO 1: 49 (SECTORS 2.10 estimates about 40: 4 / 5 / 6 / 6 / 14 / 7). Hours: Software 59.9, Gaming before the fit 47.6, after 59.9. The doc's fitted base is 0.77 of Software's Income for the whole ladder (SECTORS 2.10): the column 'base Income' is the same quantity measured.

### Parity with fit 1: Gaming hours / Software hours, per rung, in % (median over 40 seeds; mark 95 to 105)
| Profile | Skill | Garage | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO 1 | IPO 1 per-seed p10 to p90 |
|---|---|---|---|---|---|---|---|---|---|
| reference | typical | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 to 100.0 |
| dedicated | typical | 103.0 | 101.3 | 101.0 | 101.3 | 100.8 | 99.8 | 100.7 | 100.6 to 100.8 |
| dedicated | fast | 104.6 | 103.8 | 102.9 | 102.6 | 101.8 | 101.2 | 102.1 | 102.0 to 102.1 |
| dedicated | slow | 99.6 | 96.8 | 95.6 | 95.4 | 95.0 | 93.7 | 95.0 | 95.0 to 95.1 |
| regular | typical | 102.1 | 101.5 | 100.9 | 101.3 | 100.8 | 99.8 | 100.7 | 100.6 to 100.8 |
| regular | fast | 105.6 | 103.7 | 102.8 | 102.7 | 101.8 | 101.2 | 102.1 | 102.0 to 102.2 |
| regular | slow | 99.5 | 96.7 | 95.6 | 95.5 | 95.0 | 93.7 | 95.0 | 95.0 to 95.1 |
| casual | typical | 101.7 | 101.4 | 100.9 | 101.3 | 100.8 | 99.8 | 100.7 | 100.6 to 100.8 |
| casual | fast | 105.7 | 103.9 | 102.7 | 102.6 | 101.8 | 101.2 | 102.1 | 102.0 to 102.2 |
| casual | slow | 99.0 | 96.9 | 95.7 | 95.4 | 95.0 | 93.7 | 95.0 | 94.9 to 95.1 |
| heavy | typical | 100.4 | 104.8 | 96.5 | 97.2 | 98.9 | 97.9 | 99.3 | 96.8 to 99.4 |
| heavy | fast | 103.7 | 103.6 | 99.7 | 101.1 | 100.7 | 99.1 | 100.2 | 100.0 to 100.4 |
| heavy | slow | 97.6 | 95.7 | 96.4 | 92.0 | 92.2 | 91.1 | 92.9 | 91.6 to 94.3 |
| boundary | typical | 100.4 | 100.8 | 100.6 | 100.6 | 100.5 | 99.9 | 100.4 | 100.3 to 100.4 |
| boundary | fast | 103.7 | 103.7 | 102.4 | 102.3 | 101.5 | 101.3 | 101.8 | 101.8 to 101.9 |
| boundary | slow | 97.6 | 96.0 | 95.2 | 94.6 | 94.5 | 93.8 | 94.6 | 94.6 to 94.6 |
| check-in | typical | 126.1 | 115.2 | 104.8 | 105.6 | n/a | n/a | never | |
| check-in | fast | 128.4 | 116.6 | 106.0 | 106.2 | n/a | n/a | never | |
| check-in | slow | 124.4 | 113.3 | 102.6 | 103.1 | n/a | n/a | never | |

Worst deviation with fit 1: 28.4% (check-in/fast). Outside +-5%: dedicated/slow (6.3%), regular/fast (5.6%), regular/slow (6.3%), casual/fast (5.7%), casual/slow (6.3%), heavy/slow (8.9%), boundary/slow (6.2%), check-in/typical (26.1%), check-in/fast (28.4%), check-in/slow (24.4%).

### Loops 2 and 3 (regular, typical): hours of IPO 2 and IPO 3, a Gaming company in every loop, in % of Software
- IPO 1: Software 57.1 h, Gaming 57.5 h = 100.7 (100.6 to 100.8)%
- IPO 2: Software 51.5 h, Gaming 51.5 h = 99.9 (99.8 to 100.2)%
- IPO 3: Software 52.0 h, Gaming 51.9 h = 99.8 (99.7 to 100.2)%

### Fix A: Gaming's away bank pays on the Software-equivalent base (`away_fix`: 10% of the base Income of the unscaled upgrade Incomes), fit 1 beta
| Profile | Skill | Garage | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO 1 | IPO 1 per-seed p10 to p90 |
|---|---|---|---|---|---|---|---|---|---|
| casual | typical | 100.9 | 100.2 | 99.2 | 99.8 | 99.7 | 99.4 | 99.7 | 99.6 to 99.7 |
| check-in | typical | 112.0 | 101.7 | 98.1 | 98.2 | n/a | n/a | never | |

With the away fix the check-in profile is within 12.0% (check-in/typical) at the rungs it reaches.

### Fix B: smaller launch revenue (peaks x0.6: 0.09 / 0.21 / 0.36 / 0.48, cap 0.48, back catalog 0.06), refitted; the skill spread is x / (1 + f), so a smaller x spreads less
### Fit B
| Rung | Software h | Gaming h, beta 1.0 (no fit) | fitted beta | Gaming h after the fit | Gaming base Income / Software's at the end of the rung | average extra (x base) | titles launched in the rung |
|---|---|---|---|---|---|---|---|
| Garage | 1.50 | 1.30 | 0.811 | 1.51 | 0.82 | 0.21 | 4 |
| Seed | 3.98 | 3.29 | 0.776 | 3.98 | 0.84 | 0.31 | 7 |
| Series A | 6.51 | 5.51 | 0.775 | 6.51 | 0.88 | 0.31 | 8 |
| Series B | 9.02 | 7.74 | 0.728 | 9.02 | 0.88 | 0.31 | 7 |
| Series C+D | 23.84 | 20.83 | 0.746 | 23.85 | 0.89 | 0.30 | 14 |
| Pre-IPO | 15.01 | 13.15 | 0.612 | 15.02 | 0.88 | 0.30 | 9 |

Total titles to IPO 1: 49 (SECTORS 2.10 estimates about 40: 4 / 5 / 6 / 6 / 14 / 7). Hours: Software 59.9, Gaming before the fit 51.8, after 59.9. The doc's fitted base is 0.77 of Software's Income for the whole ladder (SECTORS 2.10): the column 'base Income' is the same quantity measured.

### Parity with fix B and the away fix (median over 40 seeds; mark 95 to 105)
| Profile | Skill | Garage | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO 1 | IPO 1 per-seed p10 to p90 |
|---|---|---|---|---|---|---|---|---|---|
| reference | typical | 100.4 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 to 100.0 |
| dedicated | typical | 101.6 | 100.2 | 99.4 | 99.9 | 99.9 | 99.7 | 99.8 | 99.8 to 99.9 |
| dedicated | fast | 102.8 | 102.0 | 100.8 | 100.9 | 100.6 | 100.5 | 100.8 | 100.7 to 100.9 |
| dedicated | slow | 99.4 | 97.0 | 95.7 | 96.0 | 96.0 | 95.5 | 96.0 | 95.9 to 96.1 |
| regular | typical | 100.6 | 100.3 | 99.5 | 99.9 | 99.9 | 99.7 | 99.8 | 99.8 to 99.9 |
| regular | fast | 103.8 | 102.0 | 100.8 | 101.0 | 100.6 | 100.5 | 100.8 | 100.7 to 100.9 |
| regular | slow | 99.2 | 97.0 | 95.8 | 96.0 | 95.9 | 95.5 | 96.0 | 95.9 to 96.0 |
| casual | typical | 100.8 | 100.1 | 99.5 | 99.9 | 99.9 | 99.7 | 99.8 | 99.8 to 99.9 |
| casual | fast | 103.3 | 102.1 | 100.8 | 100.9 | 100.6 | 100.5 | 100.8 | 100.7 to 100.9 |
| casual | slow | 99.2 | 97.1 | 95.9 | 96.1 | 95.9 | 95.5 | 96.0 | 95.9 to 96.0 |
| heavy | typical | 100.4 | 102.5 | 97.1 | 98.5 | 99.1 | 99.0 | 99.4 | 97.0 to 99.5 |
| heavy | fast | 102.9 | 101.9 | 99.7 | 101.1 | 99.7 | 100.0 | 100.1 | 100.0 to 100.2 |
| heavy | slow | 98.8 | 97.0 | 97.7 | 95.2 | 94.1 | 94.8 | 95.3 | 94.4 to 96.2 |
| boundary | typical | 100.4 | 100.0 | 99.7 | 99.9 | 99.9 | 99.8 | 99.9 | 99.9 to 99.9 |
| boundary | fast | 102.9 | 101.9 | 100.9 | 101.0 | 100.7 | 100.7 | 100.9 | 100.9 to 100.9 |
| boundary | slow | 98.6 | 96.7 | 96.0 | 95.9 | 96.0 | 95.6 | 96.0 | 95.9 to 96.0 |
| check-in | typical | 107.0 | 101.4 | 98.8 | 98.9 | n/a | n/a | never | |
| check-in | fast | 107.0 | 102.3 | 99.4 | 99.6 | n/a | n/a | never | |
| check-in | slow | 105.7 | 99.6 | 96.7 | 96.9 | n/a | n/a | never | |

Worst deviation with fix B and the away fix: 7.0% (check-in/typical). Outside +-5%: heavy/slow (5.9%), check-in/typical (7.0%), check-in/fast (7.0%), check-in/slow (5.7%).

**Result.** Fit 1 (the doc's rule): every rung of every schedule at the typical skill is inside +-5% except the profiles named above. Worst 28.4% (check-in/fast): FAIL (check-in, which pays only the away bank; the fast and slow skills are marginal at +-6%). With fix B and the away fix the worst is 7.0% (check-in/typical): marginal.


### S4. Bots in two sectors: PASS

**Finding.** The task-bot (24/7, perfect, held back only by the reward budget) needs **10.4 days to IPO 1 in Software and 10.4 days in Gaming**, whatever launch policy it uses (edge +0.2% / +0.4% / -0.2%; mark: no sector more than 5% faster for a bot). The pulse-bot is 3-5% *slower* in Gaming (its progress is mostly the away bank, which is lower in Gaming, see S3 fix A). A macro never gets to the IPO in either sector: graded answers are the only engaged clock, and Pitch, Launch and Update never set it, so it has no work, no revenue and no engaged seconds. Nothing proposed.

**Assumption.** The bot answers every Gaming task perfectly and picks the best of the doc's policies; Gaming's task bonus equals Software's (assumption in S3).

## S4. Bots in two sectors (docs/CUSTOMIZE_PROPOSAL.md 5.5, docs/SECTORS_PROPOSAL.md 4, 2.9)
Time to IPO 1 for a player who is online 24/7 (task-bot: answers every task perfectly, so the reward budget is its ceiling; pulse-bot: 3 minutes of tasks every 2 hours; macro: input only, answers no task), 10 seeds. Valuation weights: 3 engaged hours a day at 100%, then 5% (day starts 08:00 UTC). In Gaming a bot may choose the best launch policy; its sector verbs (Pitch, Launch, Update) never make it engaged, so a macro has no work, no revenue and no engaged clock. 'Edge' = how much faster than the same bot in Software (positive = Gaming is faster for the bot); the mark is that no sector gives a bot more than 5%.

| Player | Sector / policy | Engaged hours to IPO 1 | Days to IPO 1 | Edge over Software (days) |
|---|---|---|---|---|
| task-bot (24/7, perfect) | Software | 249.9 | 10.4 | - |
| task-bot (24/7, perfect) | Gaming, Hit (typical) | 249.5 | 10.4 | +0.2% |
| task-bot (24/7, perfect) | Gaming, Smash, update under half | 248.9 | 10.4 | +0.4% |
| task-bot (24/7, perfect) | Gaming, Smash, every update | 250.3 | 10.4 | -0.2% |
| pulse-bot (3 min every 2 h) | Software | 37.9 | 63.2 | - |
| pulse-bot (3 min every 2 h) | Gaming, Hit (typical) | 39.3 | 65.5 | -3.7% |
| pulse-bot (3 min every 2 h) | Gaming, Smash, update under half | 39.0 | 65.0 | -2.9% |
| pulse-bot (3 min every 2 h) | Gaming, Smash, every update | 40.0 | 66.6 | -5.4% |
| macro (input only) | Software | never | never | - |
| macro (input only) | Gaming, Hit (typical) | never | never | - |
| macro (input only) | Gaming, Smash, update under half | never | never | - |
| macro (input only) | Gaming, Smash, every update | never | never | - |
| dedicated human, typical (scale) | Software | 57.1 | 30.0 | - |
| dedicated human, typical (scale) | Gaming, Hit (typical) | 57.4 | 30.0 | -0.1% |
| dedicated human, typical (scale) | Gaming, Smash, update under half | 56.8 | 29.8 | +0.8% |
| dedicated human, typical (scale) | Gaming, Smash, every update | 58.5 | 30.8 | -2.5% |

**Result.** The best edge any sector gives a bot is +0.4% (mark: at most 5%): PASS. A macro never reaches the IPO in either sector (graded answers are the only engaged clock; verbs never set it). What the bot gets in Gaming over a human is the S9 spread between launch policies, not a new exploit: it pays nothing without graded answers.

### S5. Hopping between sectors: PASS

**Finding.** Ten IPOs take **543 engaged hours in Software, 544 in Gaming and 543-544 alternating** (either order): alternating is never more than 0.1% off either single sector and gains nothing (mark: under 3%). The reason is the S3 fit: with parity within 1% at the typical skill nothing is gained by switching, and the seed (10% / 25%) is the same in every loop. It holds with the doc's numbers, not only the fitted ones; no change proposed. If S3's fix B is adopted the sectors stay within the same margin (S3 table).

## S5. Hopping between sectors (docs/CUSTOMIZE_PROPOSAL.md 5.5, docs/SECTORS_PROPOSAL.md 4)
Regular player, typical skill, 10 seeds, 10 IPOs, with the placeholder seed (10% / 25%) at every founding; kept employees carry over, a Gaming company starts with an empty title cycle. Cell = total engaged hours to IPO 10, median (p10 to p90); the mark is that alternating is not faster than the faster single sector by 3% or more.

| Strategy | Hours to IPO 10 | IPO 1 | IPO 2 | IPO 5 | IPO 10 (that loop) |
|---|---|---|---|---|---|
| Software only | 543 (543 to 543) | 57.1 | 107.9 | 262.0 | 61.7 |
| Gaming only | 544 (544 to 544) | 57.5 | 108.3 | 262.5 | 61.7 |
| alternate, Software first | 543 (543 to 543) | 57.1 | 107.9 | 262.1 | 61.7 |
| alternate, Gaming first | 544 (543 to 544) | 57.5 | 108.3 | 262.5 | 61.6 |

| Alternating strategy | against Software only | against Gaming only | gain over the faster one |
|---|---|---|---|
| alternate, Software first | +0.03% | -0.09% | -0.03% |
| alternate, Gaming first | +0.10% | -0.03% | -0.10% |

**Result.** Alternating gains at most +0.00% over the faster single sector (mark: under 3%): PASS. The two single sectors differ by 0.12%.


### S9. Launch policy: launch-spam FAIL (+1.7% against the mark of 1%); the other marks PASS

**Finding.** Hours for the regular typical player against Software: Smash +2.6% (doc's estimate 54 h = 5% *faster*; measured 58.5 h), Hit +0.7% (57.5 h, the fit), Solid +8.3% (61.8 h; doc 63), Flop +14.8% (65.5 h; doc 69), never ship +25.6% (71.6 h; doc 74). **Marks: Smash at most 5% faster PASS (it is not faster at all); Solid at most 12% slower PASS (+9.3% in the worst profile); Flop at most 25% slower PASS (+15.5%).** The order is the doc's, the spread is narrower than the doc's estimate by division.

**Smash is at best a 1% choice.** With the doc's rule 'every update' Smash is slower than Hit for every value of the doc's missing number (the extra polish, as a multiple of the work, that reaches Smash): at 0.8 it equals Hit, at 1.5 it is 1.8% slower, at 3.0 it is 5.3% slower, and its peak (0.8) already sits on the cap of 0.8. With the smarter rule (update when revenue is under half the peak) Smash at 1.5 is -0.4% against Software, i.e. 1.1% *faster* than Hit: a real but tiny choice, far under the mark of 5%. If the owner wants Smash to matter, the cap must go above 0.8 and the update levels must not be wasted by an 'every update' rule.

**Launch-spam (FAIL).** A player who only builds Game Jams (the smallest scope) and polishes them to Hit is **1.7% faster than the typical Hit player** (mark: at most 1%). Under the doc's own table small titles earn more per build second (a Game Jam returns 0.77 base-seconds of revenue per build second, a Flagship 0.38), so the cheapest scope wins. Solid and Flop spam are slower (-5.1%, -11.4%). **Smallest changes:** the per-title bound of SECTORS 2.4 with **k = 0.4** (a title's total revenue at most 0.4 x its build seconds x base Income) brings spam to +0.4% (k = 0.5 and 0.6 do not bind); half-lives proportional to the work (20 / 40 / 60 / 80 / 120 minutes instead of 20 / 30 / 40 / 50 / 60) bring it to 0.0%. Both re-fitted so the typical player is still equal to Software.

**Update timing: PASS.** Best against worst is 1.6 points (updating when revenue is under half the peak is best; never updating +2.3%, updating at every cooldown +2.2%, because early updates waste the falling levels 70 / 60 / 50 / 40). The doc's 'every update' for Smash is the wasteful rule.

**With S3's fix B** (peaks x0.6) and proportional half-lives: Smash -4.6% (slow player), Solid +5.9%, Flop +10.4%, Jam-Hit spam +0.0%: all marks pass with more margin, and policies matter less.

**Assumptions.** The five policies as in the S3 assumptions; Solid and Flop never update (alternative not run: an updating Solid player would be about 1.6 points closer to Software); 'Flop' = shipping at content complete with no Fun, Polish, trend or trailer.

## S9. Launch policy (docs/SECTORS_PROPOSAL.md 2.10, 4)
Gaming with the fit-1 beta of S3 (0.72, 0.66, 0.65, 0.59, 0.61, 0.4) (fitted on the Hit policy), IPO 1, 20 seeds per cell, engaged hours; cell = Gaming hours as a change against Software for the same profile and seeds (positive = slower), median (p10 to p90). Marks: Smash at most 5% faster (>= -5); Solid at most 12% slower (<= +12); Flop at most 25% slower (<= +25). The doc's own estimates of regular-player hours are in the last column.

| Policy | regular typical | dedicated typical | casual typical | regular fast | regular slow | regular typical, hours | doc estimate, hours |
|---|---|---|---|---|---|---|---|
| Polish to Smash, every update | +2.6% (+2.5% to +2.6%) | +2.6% (+2.5% to +2.7%) | +2.6% (+2.5% to +2.6%) | +3.9% (+3.8% to +4.0%) | -2.7% (-2.8% to -2.7%) | 58.5 | 54 |
| Polish to Hit (typical, the fit) | +0.7% (+0.6% to +0.8%) | +0.7% (+0.6% to +0.8%) | +0.7% (+0.7% to +0.8%) | +2.1% (+2.0% to +2.2%) | -5.0% (-5.0% to -4.9%) | 57.5 | 57 |
| Ship at content complete (Solid) | +8.3% (+8.1% to +8.3%) | +8.3% (+8.2% to +8.3%) | +8.2% (+8.2% to +8.3%) | +9.3% (+9.1% to +9.3%) | +3.9% (+3.8% to +3.9%) | 61.8 | 63 |
| Rush every title (Flop) | +14.8% (+14.8% to +14.9%) | +14.8% (+14.8% to +14.9%) | +14.8% (+14.8% to +14.9%) | +15.5% (+15.4% to +15.6%) | +11.7% (+11.6% to +11.8%) | 65.5 | 69 |
| Never ship | +25.6% (+25.4% to +25.7%) | +25.6% (+25.5% to +25.6%) | +25.6% (+25.5% to +25.7%) | +25.5% (+25.4% to +25.6%) | +25.3% (+25.2% to +25.4%) | 71.6 | 74 |

(Smash with the smarter update rule, 'when under half the peak': -0.4% (-0.5% to -0.3%) for the regular typical player.)

Worst cell per mark: Smash -2.7% (mark >= -5), Solid +9.3% (mark <= +12), Flop +15.5% (mark <= +25).

### What Smash costs: extra polish needed for Smash, as a multiple of the work (the doc gives no number; Hit is 0.5 by SECTORS 2.10)
| tau_smash | Smash vs Software (regular typical) | Smash vs Hit | titles to IPO 1 (Smash) |
|---|---|---|---|
| 0.8 | +0.7% (+0.6% to +0.7%) | -0.0% (-0.1% to +0.0%) | 33 |
| 1.0 | +1.3% (+1.2% to +1.4%) | +0.6% (+0.5% to +0.6%) | 31 |
| 1.5 | +2.6% (+2.5% to +2.6%) | +1.8% (+1.8% to +1.9%) | 28 |
| 2.0 | +3.8% (+3.7% to +3.9%) | +3.1% (+3.0% to +3.1%) | 25 |
| 3.0 | +6.0% (+5.9% to +6.1%) | +5.3% (+5.2% to +5.3%) | 20 |

### Launch-spam: only Game Jams, the smallest scope, all the way up the ladder (a title every 15 to 25 engaged minutes), against the typical Hit player
| Spam policy | Gaming vs Software (regular typical) | gain over the typical Hit player |
|---|---|---|
| Jam Solid, no updates | +6.2% (+6.1% to +6.2%) | -5.1% (-5.2% to -5.1%) faster |
| Jam Solid, update every cooldown | +6.2% (+6.1% to +6.2%) | -5.1% (-5.2% to -5.1%) faster |
| Jam Hit, update when under half | -1.0% (-1.1% to -0.9%) | +1.7% (+1.7% to +1.8%) faster |
| Jam Hit, update every cooldown | -1.0% (-1.1% to -0.9%) | +1.7% (+1.7% to +1.8%) faster |
| Jam Flop (rush), no updates | +13.7% (+13.6% to +13.8%) | -11.4% (-11.5% to -11.4%) faster |

### Update timing: the Hit player with each rule for when to use a Live Update (best against worst)
| Rule | Gaming vs Software (regular typical) |
|---|---|
| never update | +2.3% (+2.3% to +2.4%) |
| only when revenue is under a quarter of the peak | +2.3% (+2.3% to +2.4%) |
| when under half the peak (typical) | +0.7% (+0.6% to +0.8%) |
| every time the cooldown allows | +2.2% (+2.2% to +2.3%) |

### Fix for launch-spam: each fix is refitted (beta) so that the typical Hit player is again equal to Software, then the spam is measured
| Fix (placeholder changed) | fitted beta | typical Hit vs Software | Jam Hit spam: gain over typical Hit | Jam Solid spam: gain |
|---|---|---|---|---|
| none (doc as written) | (0.72, 0.66, 0.65, 0.59, 0.61, 0.4) | +0.7% (+0.6% to +0.8%) | +1.7% | -5.1% |
| per-title cap k = 0.6 (SECTORS 2.4 'k') | (0.72, 0.68, 0.63, 0.59, 0.6, 0.41) | +0.7% (+0.7% to +0.8%) | +1.8% | -5.1% |
| k = 0.5 | (0.72, 0.7, 0.64, 0.59, 0.61, 0.4) | +0.7% (+0.6% to +0.8%) | +1.9% | -5.0% |
| k = 0.4 | (0.73, 0.74, 0.64, 0.6, 0.6, 0.4) | +0.7% (+0.7% to +0.7%) | +0.4% | -4.5% |
| half-lives proportional to the work: 20 / 40 / 60 / 80 / 120 min | (0.72, 0.63, 0.64, 0.56, 0.56, 0.36) | +0.8% (+0.7% to +0.8%) | +0.0% | -6.7% |

### The same marks with S3's fix B (peaks x0.6, cap 0.48, back catalog 0.06; beta refitted) and the half-life fix for launch-spam
| Policy | regular typical | regular fast | regular slow |
|---|---|---|---|
| Polish to Smash, every update | -0.2% (-0.4% to -0.2%) | +0.8% (+0.6% to +0.8%) | -4.6% (-4.6% to -4.5%) |
| Polish to Hit (typical, the fit) | +0.5% (+0.5% to +0.5%) | +1.4% (+1.4% to +1.5%) | -3.5% (-3.6% to -3.5%) |
| Ship at content complete (Solid) | +5.2% (+5.1% to +5.3%) | +5.9% (+5.8% to +6.0%) | +2.1% (+2.0% to +2.2%) |
| Rush every title (Flop) | +10.0% (+9.9% to +10.0%) | +10.4% (+10.3% to +10.4%) | +7.9% (+7.8% to +8.0%) |
| Never ship | +16.6% (+16.6% to +16.8%) | +16.6% (+16.6% to +16.7%) | +16.5% (+16.4% to +16.6%) |

With fix B and proportional half-lives: Smash -4.6%, Solid +5.9%, Flop +10.4%, Jam-Hit spam gain +0.0%.

**Result.** Smash PASS (-2.7%); Solid PASS (+9.3%); Flop PASS (+15.5%); launch-spam best gain +1.7% (FAIL, mark 1%; first fix that meets it: k = 0.4); update timing spread 1.6 points (PASS, mark 5).

### S10. Cadence: Gaming's cycle gap FAIL (45 min against 15), fixed by a checkpoint; Software outside Series C+D cannot be confirmed

**Finding.** With only timed events (purchases, milestones, board / publisher requests, and in Gaming the cycle's own decisions), **Gaming has a moment every 12 minutes or less in every rung except the Pre-IPO (every 12 min, gap 45) and Series C+D (gap 43-45)**, and no gap over 45 engaged minutes: PASS at the limit. The title cycle alone leaves gaps of 8 / 15 / 22 / 30 / 45 / 45 minutes (Flagship: Pitch, then 45 min to Playtest, 45 to content complete, 45 of polish): **the mark "longest wait between decisions under 15 minutes" FAILS from Series A on.** The smallest change is a *checkpoint verb* (a visible choice such as which meter to fill, never a task, so it never makes anyone engaged) every **12 engaged minutes** while a title is in development: the longest wait drops to 12 minutes in every rung. Software's Series C+D gap is the 45 minutes LONG_GAME states; the sim has no times for the tasks, products, decor and titles of the other rungs, so their timed gaps (58 to 576 min) are only upper bounds and the 45-minute mark cannot be confirmed for Software from this sim.

## S10. Cadence: moments per hour and the longest gap (docs/SECTORS_PROPOSAL.md 4; docs/LONG_GAME_PROPOSAL.md 4)
Always-engaged reference player, IPO 1 (the engaged hours of each event come from the run). A moment = a timed event: an item bought (upgrade, office, desk, hire), a valuation milestone and a board / publisher request (Series C+D), and in Gaming the title-cycle decisions: Pitch, Playtest fix, content complete (ship or polish), Launch and each Live Update. Untimed content (tasks that appear, products, decor, titles) is not in the sim, so every gap is an upper bound. 'Cycle only' = the gaps between title-cycle decisions alone.

| Rung | Hours | Software: moments per hour | longest gap, min | Gaming: moments per hour | longest gap, min | Gaming, cycle only: longest gap, min | Gaming with a checkpoint every 12 min: longest gap, min |
|---|---|---|---|---|---|---|---|
| Garage | 1.5 | 7.3 | 18 | 20.0 | 8 | 8 | 8 |
| Seed | 4.0 | 2.8 | 58 | 11.6 | 15 | 15 | 12 |
| Series A | 6.5 | 2.0 | 107 | 8.1 | 22 | 22 | 12 |
| Series B | 9.0 | 1.4 | 185 | 5.9 | 30 | 30 | 12 |
| Series C+D | 23.8 | 3.0 | 45 | 7.0 | 43 | 45 | 12 |
| Pre-IPO | 15.0 | 0.9 | 576 | 4.9 | 45 | 45 | 12 |

**Result.** Software: the Series C+D gap is 45 min (LONG_GAME's 45 with the board requests); the other rungs' timed gaps (up to 576 min) are upper bounds, because their tasks, products, decor and titles have no time in the sim, so the 45-minute mark cannot be confirmed for Software outside C+D from this sim. Gaming: longest gap between any timed moments 45 min (mark: no gap over 45 minutes: PASS, at the limit). Gaming's longest wait between decisions of the title cycle alone is 45 min (mark: under 15: FAIL); with a checkpoint verb every 12 engaged minutes while a title is in development it is 12 min: PASS.


## 5. Assumptions (where a doc is ambiguous, and what was run instead)

Nothing below was changed silently; each open choice is either swept in the sim named, or marked as a plain assumption.

**Gaming's title cycle (SECTORS 2.2-2.4; S3, S4, S5, S7, S8, S9, S10)**
- *Scope factor.* The peak table is given for the Game Jam and "same x scope" for the others; the factor is not given. Run with **1.0 for every scope**. (With a factor above 1 the cap of 0.8 would bind for every Hit from the Indie on.)
- *Fun and Polish* are not simulated as two meters. The Score is a **polish curve**: Score 55 at content complete (Solid), 70 after polishing 0.5 x the work (Hit: SECTORS 2.10 "work plus half as much polish"), 90 after **1.5 x** (Smash: the doc gives no number; swept 0.8 to 3.0 in S9), then flat. Trend (+15) and trailer (+10) are always achieved by a player who plans; fans add +5 per earlier Hit up to +10; a Flop is a title shipped with no Fun, Polish, trend or trailer (Score 15).
- *Work time* per scope is the table's "typical work" (15 / 30 / 45 / 60 / 90 engaged minutes) whatever the team; the doc's "work per second = founder + a fixed amount per head" has no number.
- *Updates* are a free verb after a 10-engaged-minute cooldown; they restore revenue to 70 / 60 / 50% of the peak (doc) and then **40, 30 ... never under 10%** (assumption; the doc only says "each later update lifts less"). Policies: Smash "every update" = every time the cooldown allows; **Hit and typical = update when revenue is under half the peak** (assumption); Solid and Flop never update.
- *Per-title bound* (SECTORS 2.4 "k x build seconds x base Income"): no k is given, so it is **off** in the main runs; S9 sweeps it.
- *Gaming's task bonus f equals Software's* (the engine's reward budget is the ceiling for both; the Gaming rows have no arrival rates in the doc). The S3 skill spread is the consequence.
- *Base Income:* Gaming's upgrade Incomes are scaled by one factor per rung (fitted, S3); hires and desks are unchanged. The extra never enters the away bank, `baseIncome` or the task rewards (SECTORS 2.4).
- *The IPO* ends the title in development and the live title (no refund); `sx` starts empty.

**S1 / S2.** "The new first rung's prices" = the sum of the Garage rung's prices at the new loop's StageScale (the other reading, c% of the valuation that opens Seed, is in S1). A "decorator" has no leftover Cash at the IPO; the heavy decorator (10% of all Cash on furniture) is my number: furniture prices are not in the docs. The bonus multiplies spendable Cash where the passes do (so also task Cash and away pay), never the valuation.

**S6 / S7.** *T* is **measured**, not taken from LONG_GAME: the median stamp-clock hours of the regular typical player per loop with a typical raise (Medium at every round) and the placeholder seed (CUSTOMIZE open question 1). A *profile* is a population: each seed's task skill is x(1 +- 20%) (my number; without it every player of a profile is the same person). *Fast* = expert at tasks, *slow* = the task bonus x0.5 (LONG_GAME's own sensitivity row), *dedicated* = 2 h a day. A *replay* = IPO 2, 3, 4 of the same sector. *Hunting* = go public only when the ratio has reached 1.25 (or Platinum is out of time); *ready* = go public at once. The pass-share shrink uses the whole run with the pass. S7 reads "within 10%" as hours (and, separately, points per hour), and "the bot never above a dedicated human" per stamp-clock hour (per day the bot is faster by design, LONG_GAME section 2).

**S8.** *Policies* none / Small / Medium / Large every round; *best-per-stage* = a coordinate search (two passes, last stage first) over the 4^5 choices for the fewest hours to IPO 3, once with Shares valued (the speed perk) and once with the shop complete and total dilution at most 3,000 bp. *Shop complete* = the +25% speed lump from the first loop and Shares worth nothing; *Shares valued* = the lump (154 Shares, LONG_GAME's own estimate) is the only sink, so Shares are worth little in this model. A raised round is Cash only (asserted: valuation, lifetime and best are unchanged). The converter is checked by counting what is still unowned at the IPO; the alt feeds 3 poach-ins per run (R2) that do not carry over. "Raising the last open round" = the Pre-IPO round raised at 0 / 50 / 90 / 99% of its stage. *Today's 5 stages* use the Player model (real IpoConfig, egg rolls; runs are not paired).

**S10.** A moment = a **timed** event (a purchase, a milestone, a board request, and in Gaming Pitch / Playtest / content complete / Launch / Update). Untimed content is not in the sim, so Software's non-C+D gaps are upper bounds.

**Everything.** Same random stream for the same seed and profile, so two options differ only by what they change; steps of 20 s; the 3 h/day rule and the 08:00 UTC day as in `--long`. Seeds per cell: S1 and S2 40, S3 40 (check-in 10), S4 and S5 10 (24/7 runs are long), S6 population 16, S7 8, S8 10 (5 for ten loops), S9 20; S10 is one deterministic reference run.

## 6. Output of the default run and of `--long`: unchanged

`python tools/economy_sim.py > after.txt` and `python tools/economy_sim.py --long > after_long.txt` were compared byte for byte (`cmp`) with the output of the unmodified script on `main` `e3c9e67`: **identical**, before the first commit and again before the last. The only edit to existing code is one line in `run()` (`player_cls`, default `Player`) so that S8 can run today's economy with rounds; with the default it builds the same object. Everything else is new code after `report_long` and in `main()`'s argument list.

## 7. What was NOT modeled

- Egg rolls, hatch timers and poaching in the long-game ladder (the hire is the planned creature, as in `--long`), HR levels, eggs and the converter beyond "nothing is left to buy"; real poaching between people; D9 fixed-order hires.
- Fun and Polish as separate meters, the Playtest card's effect, the Trailer's three beats, the trend schedule and genres (trend is always matched), game names, reviews; real Gaming task rows (their arrival rates are not in the doc).
- Any perk other than the one speed lump, offline pay above the away bank, the daily calendar, weekly events, Cash packs.
- Mixed populations (a player who changes skill, schedule or pass during a run), passes bought mid-run (pass share is 0 or 1), players who leave, fun, retention, and the social side of the leaderboard (Collection is computed per player, not ranked).
- Fintech and Biotech; the Studio UI limits; the real task bonus (f is the model's Monte Carlo; LONG_GAME's gate G1 measures it).
- The real server's rules about shared saves between Studio and live.
