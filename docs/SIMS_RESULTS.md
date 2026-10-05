# Sims S1-S10: results (design-doc sims, run before any build)

Run 2026-10-05, branch `sims-two-sectors`, script `tools/economy_sim.py` (new code only; no `.lua` file, no `tools/daily_test.py`, no design doc touched). Numbers come from `python tools/economy_sim.py <flag>` (each sim has its own flag, default OFF; `--runs N` sets the seeds, default 40). Every number in the three design docs is a **placeholder**; this file measures them, says PASS / FAIL / marginal against the mark the doc gives, and for each FAIL or marginal result gives the smallest change to the placeholder and the re-run with it.

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

(Summary table of all ten sims: section 4, written at the end.)

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
