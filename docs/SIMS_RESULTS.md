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
| **S4 bots** | `--s4` | A task-bot (and a macro, and a pulse-bot) in each sector | no sector faster for a bot (the docs give **no tolerance**; the 5% used in the first version of the results was invented) | CUST:122, SECT:158, PR 12 CUST:164 |
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
- **Profiles.** Schedules: `dedicated` (2 h a day), `regular` (1 h), `casual` (3 h a week), the `task-bot`, `pulse-bot`, `macro` and `reference` of `--long`, plus `heavy` (5 h a day) and `boundary` (a session across 08:00 UTC) added here to exercise the 3 h cap and the day boundary. Skills: `typical` (the default), **fast** = `expert` at tasks, **slow** = the task bonus x0.5 (LG:12's own sensitivity row; an earlier draft cited LG:6). Passes: none, VIP (x1.5 Cash), 2x Cash, Cash + VIP (x3), Shareholder (x2 Shares), Cash + Shareholder.
- **Valuation is base Cash** (LG:93), and a pass, the bonus, the seed and a round change spendable Cash only.


## Summary of the results (details in section 3)

| Sim | Flag | Verdict | One-line finding |
|---|---|---|---|
| S1 seed | `--s1` | **PASS** | The seed is worth about 1.2% of a loop (mark 5%); the cap is the only thing that binds, `s` never does. |
| S2 bonus | `--s2` | **PASS** | At +10 points the run takes 96.6% of the no-bonus hours (no pass), 99.0% with 2x Cash (mark 95%+). |
| S3 parity | `--s3` | **FAIL as written, marginal after 2 changes** | Typical skill: every schedule within +-3% except the added `heavy` profile (4.8%; 5.1% on seeds 500-519: noise-level, so the typical-skill PASS is thin). Slow and fast players are 6% off, check-in 26% off, the pulse-bot 12.8% off in the Garage rung; `macro`, `task-bot` and `pulse-bot` had no per-rung parity before. Fix B (launch revenue x0.6) plus an away-bank fix brings all but two cells inside +-5%. |
| S4 bots | `--s4` | **FAIL by +0.38% on the doc's strict mark; PASS within an invented 5%** | Task-bot 10.4 days in both sectors, Gaming at most +0.38% faster (Smash, update under half); a macro never finishes in either. |
| S5 hopping | `--s5` | **PASS** | 10 IPOs: 543 h Software, 544 h Gaming, alternating 543-544 h (mark 3%). |
| S6 tiers | `--s6` | **FAIL** | Gold 50% is a tautology (46% on new players with the same T; 69% / 52% against LONG_GAME's T); **Platinum 0%** for typical, fast, slow and pass owners under the doc's rule; 1.0 T / 1.20 helps only fast players (typical 0%), 1.1 T / 1.25 gives typical 29% / fast 69%; the Cash pass shortens a replay by 6%, not 15%, so the shrink must be 6%. |
| S7 board | `--s7` | **PASS in hours; FAIL in points (this sim's own reading); the bot PASSES on the doc's own metric, fails only on an invented one** | New sector 99.6% of a replay's hours; points per hour 2x apart (a sector caps at 3 points); **Collection total: bot 4004 = human 4004 at the median (never above: PASS)**; per "Collection per stamp-clock hour" (invented) the bot is +7.5% and a heavy human (5 h a day) +4.9%: the cause is more than 3 h a day, not being a bot. |
| S8 round size | `--s8` | **mixed** | Tables reproduced, nothing dominated, Large saves 5.0-5.6% of a loop; but the price per hour is not constant (Pre-IPO Large 31.8 against 2.5, 12.7 times), the maximum is best for everyone except 2x Cash owners, and a table fitted to the measured savings never makes the stake line bite. |
| S9 launch policy | `--s9` | **FAIL (launch-spam)** | Smash +2.6% with 'every update' (-0.4% with the smarter rule: about 1% faster than Hit), Solid +8.3%, Flop +14.8% all inside their marks; Game-Jam spam is 1.7% faster than the typical player (mark 1%); k = 0.4 fixes it. |
| S10 cadence | `--s10` | **FAIL (cycle gap)** | Gaming has no gap over 45 min but its own cycle leaves 45-minute waits (mark: under 15); a 12-minute checkpoint verb gives 12. Software outside Series C+D cannot be confirmed (untimed content). |


## 3. Results

(Summary table of all ten sims: the summary above; the placeholder numbers that must change: section 4 below.)

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

**Finding.** The Gaming title cycle of SECTORS 2.2-2.4 (Hit policy, doc numbers) can be fitted so that Software and Gaming take the same hours in every rung for the reference player, and then **every schedule at the typical skill stays within +-3.0%** (dedicated, regular, casual, boundary: 0.2% to 3.0%, the worst being the Garage rung of the dedicated player; IPO 2 and 3 within 0.2%) **except `heavy`, 4.8% in one noisy rung**. That is the doc's rule and it passes, **but the typical-skill PASS is thin and rests on a profile this sim added**: the 4.8% of `heavy` (5 h a day, not a `LONG_PLAYERS` profile) is 0.2 point inside the mark, and on a second set of 20 seeds (500-519) the same row is **5.1%, outside it**. Treat the `heavy` row as noise-level around the mark: neither a pass nor a fail (every other typical-skill row stays at 3.0% or less on both seed sets).

**The profiles the doc names are not all covered.** SECTORS 4 (SECT:157) asks for parity at "every `LONG_PLAYERS` profile". `LONG_PLAYERS` = dedicated, regular, casual, check-in, macro, task-bot, pulse-bot, reference. The per-rung tables cover dedicated, regular, casual, check-in and reference (plus `heavy` and `boundary`, added here); **`macro`, `task-bot` and `pulse-bot` had no per-rung parity**. `macro` answers no task, so it never finishes a rung and there is nothing to compare. Run now (typical skill only, a bot's skill is fixed by its profile): **task-bot is within 3.5%** (Garage 103.5, IPO 1 99.8), and **pulse-bot is 12.8% off in the Garage rung and 3.7% at IPO 1 under the doc's rule: FAIL** (its progress is mostly the away bank, which is lower in Gaming, S3 fix A); with fix B and the away fix both bots are within 2.6%. It fails in three places:

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

### The LONG_GAME profiles that have no per-rung parity above
SECTORS 4 asks for parity at 'every `LONG_PLAYERS` profile'. LONG_PLAYERS = dedicated, regular, casual, check-in, macro, task-bot, pulse-bot, reference. The tables above cover dedicated, regular, casual, check-in, reference (and `heavy` and `boundary`, added here); **not covered: macro, task-bot, pulse-bot**. `macro` answers no task, so it never finishes a rung (nothing to compare). `task-bot` and `pulse-bot` are run here (a bot's skill is fixed by its profile, so the typical-skill row only; fewer seeds, they are 24/7 runs):

Fit 1 (the doc's rule):
| Profile | Skill | Garage | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO 1 | IPO 1 per-seed p10 to p90 |
|---|---|---|---|---|---|---|---|---|---|
| task-bot | typical | 103.5 | 100.3 | 99.8 | 99.9 | 99.6 | 100.0 | 99.8 | 99.8 to 99.8 |
| pulse-bot | typical | 112.8 | 110.2 | 103.3 | 103.1 | 103.2 | 103.0 | 103.7 | 103.7 to 103.8 |

Fix B and the away fix:
| Profile | Skill | Garage | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO 1 | IPO 1 per-seed p10 to p90 |
|---|---|---|---|---|---|---|---|---|---|
| task-bot | typical | 102.6 | 100.2 | 99.9 | 99.9 | 99.8 | 100.0 | 99.9 | 99.9 to 99.9 |
| pulse-bot | typical | 101.1 | 101.9 | 98.7 | 99.6 | 99.5 | 100.1 | 99.8 | 99.7 to 99.8 |

The bots: worst deviation 12.8% (pulse-bot/typical) with fit 1, 2.6% (task-bot/typical) with fix B and the away fix.

### Typical skill on a second set of seeds (fit 1, seeds 500-519; mark 95 to 105): is the typical-skill PASS stable?
| Profile | Skill | Garage | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO 1 | IPO 1 per-seed p10 to p90 |
|---|---|---|---|---|---|---|---|---|---|
| reference | typical | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 to 100.0 |
| dedicated | typical | 100.9 | 101.4 | 101.0 | 101.2 | 100.8 | 99.8 | 100.7 | 100.6 to 100.7 |
| regular | typical | 102.7 | 101.2 | 101.0 | 101.3 | 100.8 | 99.8 | 100.7 | 100.6 to 100.8 |
| casual | typical | 102.6 | 101.3 | 101.0 | 101.3 | 100.8 | 99.8 | 100.7 | 100.6 to 100.8 |
| heavy | typical | 100.4 | 100.6 | 99.7 | 97.7 | 99.4 | 94.9 | 99.2 | 96.4 to 99.4 |
| boundary | typical | 100.4 | 100.8 | 100.6 | 100.4 | 100.5 | 99.9 | 100.4 | 100.3 to 100.4 |
| check-in | typical | 126.7 | 114.8 | 104.7 | 105.5 | n/a | n/a | never | |

Typical skill without check-in, worst row: seeds 0-39: 4.8% (heavy/typical); seeds 500-519: 5.1% (heavy/typical). Rows over 5% on seeds 500-519: heavy/typical (5.1%); on seeds 0-39: none.

**Result.** Fit 1 (the doc's rule): worst 28.4% (check-in/fast): FAIL. Outside +-5%: check-in, which pays only the away bank: check-in/typical (26.1%), check-in/fast (28.4%), check-in/slow (24.4%); the fast and slow skills: dedicated/slow (6.3%), regular/fast (5.6%), regular/slow (6.3%), casual/fast (5.7%), casual/slow (6.3%), heavy/slow (8.9%), boundary/slow (6.2%); any other profile: none. With fix B and the away fix the worst is 7.0% (check-in/typical): marginal. Outside +-5%: check-in: check-in/typical (7.0%), check-in/fast (7.0%), check-in/slow (5.7%); fast / slow skills: heavy/slow (5.9%); any other: none.


### S4. Bots in two sectors: tiny FAIL on the doc's strict mark (+0.38%), PASS only within a 5% tolerance the doc never gives

**Finding.** The task-bot (24/7, perfect, held back only by the reward budget) needs **10.4 days to IPO 1 in Software and 10.4 days in Gaming**, whatever launch policy it uses (edge +0.2% / +0.4% / -0.2%). **The doc's mark is "no sector faster for a bot" (CUST:122, SECT:158) with NO tolerance.** The 5% in the first version of this section (here, in the S4 table note, and in the code check `<= 5`) was invented by the sim's author; the doc says nothing of the kind. Two verdicts, both measured: (1) **strict reading of the doc: FAIL by +0.38%** (the best Gaming variant for the task-bot, Smash with "update under half the peak"; the same +0.38% in every seed, so it is the model, not noise: tiny, but not zero); (2) **within an invented 5%: PASS.** The pulse-bot is 3-5% *slower* in Gaming (its progress is mostly the away bank, which is lower in Gaming, see S3 fix A). A macro never gets to the IPO in either sector: graded answers are the only engaged clock, and Pitch, Launch and Update never set it, so it has no work, no revenue and no engaged seconds. **For the owner:** a zero-tolerance mark cannot be met by two different models (any edge above 0 fails it), so the doc should name a tolerance; the measured +0.38% is the number to judge it by. No placeholder is changed.

**Assumption.** The bot answers every Gaming task perfectly and picks the best of the doc's policies; Gaming's task bonus equals Software's (assumption in S3).

## S4. Bots in two sectors (docs/CUSTOMIZE_PROPOSAL.md 5.5, docs/SECTORS_PROPOSAL.md 4, 2.9)
Time to IPO 1 for a player who is online 24/7 (task-bot: answers every task perfectly, so the reward budget is its ceiling; pulse-bot: 3 minutes of tasks every 2 hours; macro: input only, answers no task), 10 seeds. Valuation weights: 3 engaged hours a day at 100%, then 5% (day starts 08:00 UTC). In Gaming a bot may choose the best launch policy; its sector verbs (Pitch, Launch, Update) never make it engaged, so a macro has no work, no revenue and no engaged clock. 'Edge' = how much faster than the same bot in Software (positive = Gaming is faster for the bot). The doc's mark is 'no sector faster for a bot' (CUSTOMIZE 5.5 = CUST:122, SECTORS 4 = SECT:158) with NO tolerance; the 5% that earlier versions of this file used (and the check below) is an INVENTED tolerance of this sim, not the doc's, so the result gives both readings.

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

**Result.** The best edge any sector gives a bot is +0.38% (task-bot, Gaming, Smash, update under half; per seed +0.38% (+0.38% to +0.38%)). Two verdicts: (1) the doc's mark read strictly, 'no sector faster for a bot' with no tolerance: FAIL (by a tiny margin); (2) within an invented 5% tolerance (not in the doc): PASS. A macro never reaches the IPO in either sector (graded answers are the only engaged clock; verbs never set it). What the bot gets in Gaming over a human is the S9 spread between launch policies, not a new exploit: it pays nothing without graded answers.

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


### S6. Stamp tiers: Gold PASS only as a tautology; Platinum FAIL for every kind of player; pass owners FAIL (the 15% shrink is too big)

**Finding.**
- **Gold: PASS, but the test is a tautology.** T is the median of the same 16 players (the same seeds) whose Gold rate is then measured, so exactly 50% of that player's replays are Gold whatever the economy does (mark: at least 50%): it cannot fail. Against a T the players did not set: **16 new players (seeds 100-115) with the same T: 46%**; **LONG_GAME's own T (57 / 51.5 / 52 h): 69% when the players raise Medium every round, 52% with no round** (what LONG_GAME's hours describe). A fast player gets Gold on 81% of replays, a slow one on 0%. The rate is hypersensitive: the same T gives **69% in Gaming against 50% in Software** because Gaming's replays are 0.2% faster (S3), which moves a tight population across the median.
- **Platinum: FAIL under the doc's rule (0.8 T, ratio 1.25) for every kind of player, 0% each** (mark: at least 20% of dedicated players): typical, fast, slow, 2x Cash, Shareholder and Cash + VIP owners, regular and dedicated alike (regular and dedicated come out identical per engaged hour). The hours at which the ratio is reached, as a multiple of T, median (p10 to p90): **ratio 1.25: typical 1.14 (1.05 to 1.23), fast 1.08 (0.98 to 1.17), slow 1.51 (1.43 to 1.59)**; **ratio 1.20: typical 1.11 (1.02 to 1.20), fast 1.05 (0.96 to 1.14), slow 1.47 (1.39 to 1.55), 2x Cash owners 1.12 (1.03 to 1.21) of their shrunk T = 1.05 (0.97 to 1.14) of the unshrunk T**. Nobody gets within 0.8 T: even the fastest tenth of the fast players is at 0.98 T. (The review quoted typical 1.01 / 1.09 / 1.20, fast 0.95 / 1.03 / 1.13, slow 1.38 / 1.46 / 1.54, pass owners 0.95 / 1.03 / 1.13: reproduced to within 0.02, the pass-owner row being in multiples of the unshrunk T.)
  **The earlier "smallest rule change: 1.0 T with ratio 1.20 (25%)" holds only for the dedicated fast hunter.** Under 1.0 T / 1.20 the dedicated **typical player gets 0%, the slow player 0%, the 2x Cash owner 0% and the Shareholder owner 4%**; the fast player 25% (the review found 33% with other seeds: 12 against 16 replays of 48, inside the noise). The mark is "at least 20% of dedicated players", so a rule must work for the typical dedicated player, not only the fast one. Grid (dedicated hunters, Platinum %, typical / fast / slow / 2x Cash owner with the 6% shrink): 1.0 T / 1.25: 0 / 15 / 0 / 0; 1.0 T / 1.20: 0 / 25 / 0 / 0; 1.0 T / 1.10: 25 / 67 / 0 / 25; **1.1 T / 1.25: 29 / 69 / 0 / 27**; 1.1 T / 1.20: 44 / 75 / 0 / 44; 1.2 T / 1.25: 77 / 100 / 0 / 75. **Smallest single-number change that gives at least 20% to the typical and the fast dedicated hunter: the Platinum time 0.8 T -> 1.1 T with the ratio kept at 1.25.** The slow player gets 0% under every rule tried (they need 1.47 T): that is a rule about speed, not a failure of one placeholder.
- **Pass owners: FAIL.** The 2x Cash pass shortens a replay by only **6.1%** (not the 15% LONG_GAME measures for IPO 1: kept employees make later loops less Cash-bound), so the rule "targets shrink by 15% x the share with the pass" puts Cash-pass owners at **0% Gold against 50%** (pass-blind targets: 81%). **A shrink of 6% puts them within 5 points** (54% against 50%). The **Shareholder pass** is not covered by the doc's rule and also speeds replays (2.6% / 5.3% / 8.5% at IPO 2 / 3 / 4, through the speed perks coming sooner): 83% Gold with no shrink, **48% with a 6% shrink**. Cash + VIP (x3) needs about 6% too (67% at 6%, 44% at 8%).
- **Stake.** A Large raise in every round (stake 69.6%) keeps Gold (stake minimum 55%) and, because Platinum is unreachable here, cannot lose a Platinum; the stake effect on Platinum is S8 section F.

**Placeholder changes that fix it.** Pass shrink 15% -> **6%** (Cash pass, and the same 6% for the Shareholder pass); Platinum 0.8 T and ratio 1.25 -> **1.1 T and ratio 1.25** (replaces the earlier 1.0 T / 1.20, which only helps fast players). Gold's test needs a T the players did not set (the 50% is a tautology).

**Assumptions.** T measured per loop (55.5 / 50.4 / 51.2 / 51.6 h for IPO 1-4 with a typical raise, not LONG_GAME's 57 / 51.5 / 52); a profile is a population with +-20% task skill; the pass is owned for the whole run (share 1).

## S6. Stamp tiers (docs/CUSTOMIZE_PROPOSAL.md 1.5, 5.5; docs/FUNDING_ROUNDS_PROPOSAL.md 3)
Population: 16 players per profile, task skill spread +-20% (assumption), replays = IPO 2, 3 and 4 of the same sector (loops 1-3), so 48 replays per cell. T = the regular typical player's stamp-clock hours per loop with a typical raise (Medium at every round) and the placeholder seed: **55.5, 50.4, 51.2, 51.6 h** for IPO 1-4 (the doc's LONG_GAME hours are 57 / 51.5 / 52 without a raise). Gold = within 1.0 T, ratio >= 1, stake >= 55%; Platinum = within 0.8 T, ratio >= 1.25, stake >= 70%. Targets shrink by 15% x the share of the run with the 2x Cash pass (CUSTOMIZE 1.5). 'ready' players go public the moment IPO-ready is reached (ratio 1.0); 'hunt' players keep playing until the ratio reaches 1.25 while Platinum is still possible, then go public. Cells: Gold or better % / Platinum %, Software | Gaming (Hit).

| Profile | Gold or better % (Software / Gaming) | Platinum % (Software / Gaming) |
|---|---|---|
| regular, typical, ready (the T player) | 50 / 69 | 0 / 0 |
| regular, fast, ready | 81 / 83 | 0 / 0 |
| regular, slow, ready | 0 / 0 | 0 / 0 |
| dedicated, typical, hunt | 48 / 69 | 0 / 0 |
| dedicated, fast, hunt | 81 / 85 | 0 / 0 |
| regular, typical, 2x Cash pass, targets shrunk (the rule) | 0 / 0 | 0 / 0 |
| regular, typical, 2x Cash pass, targets NOT shrunk (pass-blind) | 81 / 100 | 0 / 0 |
| dedicated, fast, hunt, 2x Cash pass, shrunk | 31 / 27 | 0 / 0 |
| regular, typical, Shareholder pass | 83 / 90 | 0 / 0 |
| regular, typical, 2x Cash + VIP (x3), shrunk 15% only | 4 / 4 | 0 / 0 |
| regular, typical, Large raise in every round (stake 69.6%) | 50 / 65 | 0 / 0 |

### Platinum for the dedicated, fast, hunting player under other time and ratio rules (Software)
| Rule | Platinum % | Gold or better % |
|---|---|---|
| 0.8 T and ratio 1.25 (the doc) | 0 | 81 |
| 0.9 T, ratio 1.25 | 0 | 81 |
| 1.0 T, ratio 1.25 | 15 | 15 |
| 1.0 T, ratio 1.20 | 25 | 25 |
| 1.0 T, ratio 1.15 | 44 | 44 |
| 1.0 T, ratio 1.10 | 67 | 67 |
| 0.8 T, ratio 1.10 | 0 | 81 |
| 0.9 T, ratio 1.10 | 4 | 81 |

### Pass owners: how much a pass really shortens a replay, and the target shrink that makes Gold equal (regular typical, Software)
| Pass | stamp-clock hours of IPO 2 / 3 / 4 as a % of no pass | Gold or better % with target shrink of 0 | 4% | 6% | 8% | 10% | 15% (the doc, Cash pass) |
|---|---|---|---|---|---|---|---|
| 2x Cash | 93.9 / 94.0 / 93.9 | 81 | 69 | 54 | 44 | 25 | 0 |
| 2x Cash + VIP (x3) | 93.5 / 93.5 / 93.4 | 88 | 69 | 67 | 44 | 31 | 4 |
| Shareholder (x2 Shares) | 97.4 / 94.7 / 91.5 | 83 | 62 | 48 | 44 | 27 | 4 |

(The player with no pass has Gold on 50%. Shrinks that land within 5 points: 2x Cash 6%, Shareholder (x2 Shares) 6%.)

### Gold: the first test is a tautology (T is the median of the same players), so Gold is also measured against T the players did not set (regular typical, Software, replays IPO 2-4)
| What T is compared with | Gold or better % |
|---|---|
| T = the median of these same 16 players (the table above): 50% by construction, PASS means nothing | 50 |
| the same T, 16 NEW players (seeds 100-115, T not refitted) | 46 |
| LONG_GAME's T (57 / 51.5 / 52 h), the players raise Medium every round | 69 |
| LONG_GAME's T (57 / 51.5 / 52 h), no round (what LONG_GAME's hours describe) | 52 |

### Platinum for every kind of player, not only the dedicated fast hunter (Software, all hunting, population of 16, replays IPO 2-4)
'Reach' = the stamp-clock hours at which the IPO-ready ratio first reaches the ratio, as a multiple of the loop's T (the shrunk T for a pass owner), median (p10 to p90) over the replays; a Platinum needs reach <= the rule's time (and a stake of 70%). Platinum % = measured by running the rule itself: the doc's rule (0.8 T, ratio 1.25, 15% shrink for the Cash pass) and the S6 fix (1.0 T, ratio 1.20, 6% shrink).
| Player | ratio 1.25 reached at (x T) | ratio 1.20 reached at (x T) | Platinum %, the doc's rule 0.8 T / 1.25 | Platinum %, the fix 1.0 T / 1.20 |
|---|---|---|---|---|
| regular, typical | 1.14 (1.05 to 1.23) | 1.11 (1.02 to 1.20) | 0 | 0 |
| dedicated, typical | 1.14 (1.05 to 1.23) | 1.11 (1.02 to 1.20) | 0 | 0 |
| regular, fast | 1.08 (0.98 to 1.17) | 1.05 (0.96 to 1.14) | 0 | 25 |
| dedicated, fast | 1.08 (0.98 to 1.17) | 1.05 (0.96 to 1.14) | 0 | 25 |
| regular, slow | 1.51 (1.43 to 1.59) | 1.47 (1.39 to 1.55) | 0 | 0 |
| dedicated, slow | 1.51 (1.43 to 1.59) | 1.47 (1.39 to 1.55) | 0 | 0 |
| regular, typical, 2x Cash pass | 1.15 (1.06 to 1.24) = 1.08 (0.99 to 1.17) x unshrunk T | 1.12 (1.03 to 1.21) = 1.05 (0.97 to 1.14) x unshrunk T | 0 | 0 |
| dedicated, typical, 2x Cash pass | 1.15 (1.06 to 1.24) = 1.08 (0.99 to 1.17) x unshrunk T | 1.12 (1.03 to 1.21) = 1.05 (0.97 to 1.14) x unshrunk T | 0 | 0 |
| regular, typical, Shareholder pass | 1.14 (1.05 to 1.24) = 1.07 (0.98 to 1.17) x unshrunk T | 1.12 (1.02 to 1.21) = 1.05 (0.96 to 1.14) x unshrunk T | 0 | 4 |
| regular, typical, 2x Cash + VIP (x3) | 1.14 (1.05 to 1.24) = 1.08 (0.99 to 1.16) x unshrunk T | 1.12 (1.02 to 1.20) = 1.05 (0.96 to 1.13) x unshrunk T | 0 | 0 |

### Other Platinum rules for the dedicated hunters (Software; Platinum %, replays IPO 2-4; the pass owner has the 6% shrink)
| Rule (time, ratio) | dedicated typical | dedicated fast | dedicated slow | dedicated typical, 2x Cash pass |
|---|---|---|---|---|
| 0.8 T, ratio 1.25 | 0 | 0 | 0 | 0 |
| 1.0 T, ratio 1.25 | 0 | 15 | 0 | 0 |
| 1.0 T, ratio 1.2 | 0 | 25 | 0 | 0 |
| 1.0 T, ratio 1.15 | 12 | 44 | 0 | 12 |
| 1.0 T, ratio 1.1 | 25 | 67 | 0 | 25 |
| 1.1 T, ratio 1.25 | 29 | 69 | 0 | 27 |
| 1.1 T, ratio 1.2 | 44 | 75 | 0 | 44 |
| 1.2 T, ratio 1.25 | 77 | 100 | 0 | 75 |
| 1.2 T, ratio 1.2 | 90 | 100 | 0 | 88 |

Rules that give at least 20% to both the dedicated typical and the dedicated fast hunter (the mark is 'at least 20% of dedicated players'): 1.0 T / 1.1, 1.1 T / 1.25, 1.1 T / 1.2, 1.2 T / 1.25, 1.2 T / 1.2.

Under the fix, Platinum is typical 0%, fast 25%, slow 0%, typical, 2x Cash pass 0% for the dedicated players (the mark is Platinum on at least 20% of dedicated players).

**Result.** Gold on 50% of the regular typical player's replays (mark: at least 50%): PASS, but that test is a tautology (T is the median of the same players: 50% by construction); on 16 new players with the same T it is 46%, against LONG_GAME's T it is 69% with a raise and 52% without. Platinum on 0% of the dedicated fast hunter's replays under the doc's rule (mark: at least 20%): FAIL; the smallest rule change that reaches 20% for that player: 1.0 T, ratio 1.20; under that fix the dedicated typical player gets 0% and the dedicated fast one 25% (the fix reaches 20% only for the fast player: FAIL for the typical one; rules that give at least 20% to both: 1.0 T / 1.1, 1.1 T / 1.25, 1.1 T / 1.2, 1.2 T / 1.25, 1.2 T / 1.2). Pass owners (2x Cash, shrunk) Gold 0% against 50% without the pass: FAIL (mark: within 5 points); pass-blind targets give 81%.

### S7. Leaderboard: new sector against replay PASS in hours, FAIL in points; the task-bot PASSES on the doc's own metric (Collection total ties) and fails only on a metric this sim invented

**Finding.**
- **Hours (the likely reading of "within 10%"): PASS.** A first Gaming company takes 49.6 h against a Software replay's 49.8 h (99.6%) at the same IPO count.
- **Points: FAIL (99% apart), on a reading that is this sim's own** (the doc does not define a points-per-hour; "within 10%" most likely means hours). A new sector always adds +1,000 (Bronze) for about one loop; a replay adds at most +1,000 once (Gold) and +1,000 once more (Platinum), and only if the player reaches the tier: the dedicated fast hunter earns 2.01 points per 100 stamp-clock hours either way for the first two loops, then **2.04 against 1.02** after four and 1.36 against 0.68 after six, because one sector can give at most 3 points. This is structural, not a number to tune: if the board must make replays as attractive as a new sector, replays need an uncapped reward; if only the first two sectors matter, the mark is met by the hours.
- **The task-bot against a dedicated human. The doc's own metric: PASS (a tie).** The mark is CUST:122 "the task-bot never above a dedicated human", and the board ranks **Collection total** (CUST:75). After 4 IPOs (alternating sectors, hunting) the bot's Collection is **4004 and the dedicated human's median is 4004** (human p10 to p90 2004 to 4004; bot 4004 to 4004): at the median the two tie, the bot is never above. An earlier version of this section said FAIL by 7%; that used a metric the docs do not contain.
- **The invented metric.** "Collection per stamp-clock hour" (Collection divided by the median stamp-clock hours of one IPO) **is this sim's own, in no doc.** On it the bot is +7.5% above the dedicated human (88.8 against 82.6), but a **heavy human (5 h a day, not a bot) is +4.9%** (86.6), 65% of the bot's edge: the edge grows with the hours played over the 3 h a day the rule counts at full value (2 h a day: the baseline, 5 h: +4.9%, 24 h: +7.5%). **So the cause is more than 3 h a day, not "being a bot"**: the 3 h/day rule weights the valuation but never Cash, so anyone who plays more than 3 h a day has bought everything long before the weighted hours run out and each weighted hour pays more.
- **Gold rates: the first table counted a loop that is not a replay.** `pk_tier_rates(first=1)` counts every loop after the first; in an alternating career loop 1 is the first Gaming company (a new sector, never Gold). Over **real replays** (IPO 3 and 4) the Gold rate is **81% for the dedicated human, 100% for the heavy human and 100% for the bot** (the earlier 54% / 67% / 67% were diluted by the non-replay loop).
- **If the owner wants the stamp clock to count raw engaged hours** (so that nobody gets faster tiers by playing over 3 h a day): the dedicated human is unchanged (Gold 54% of loops 1-3, 81% of real replays, Collection median 4004), the **heavy human falls to 0% Gold (Collection 2004) and the bot to 0% Gold (Collection 2004)**: the rule takes tiers from every player who plays more than 3 h a day, bot or human. It is not needed for the doc's own mark (the bot is not above the human on Collection), so it is an option, not a fix. Per day the bot is 2.4x faster than the human (43 against 103 days to the 4th IPO), which LONG_GAME section 2 already accepts; it still gets Bronze in every sector.

## S7. Leaderboard (docs/CUSTOMIZE_PROPOSAL.md 1.6, 5.5)
Collection = 1000 x (best stamp of each sector, Bronze 1 / Gold 2 / Platinum 3) + IPOs (CUSTOMIZE 1.6). 8 seeds per cell. Tiers use T from S6 (55.5, 50.4, 51.2, 51.6 h) and a typical raise (Medium at every round).

### 1. Hours of a new sector against a replay at the same IPO count (regular typical, placeholder seed)
| IPO | Alternating: what the loop is | hours | One sector: replay, hours | ratio |
|---|---|---|---|---|
| 2 | first Gaming company (new sector) | 49.6 | 49.8 | 99.6% |
| 3 | Software replay | 50.6 | 50.6 | 99.9% |
| 4 | first Gaming company (new sector) | 50.8 | 51.0 | 99.6% |
| 5 | Software replay | 51.2 | 51.2 | 100.0% |

### 2. Collection points per 100 stamp-clock hours: seeking new sectors against replaying one (dedicated, fast, hunting for Platinum)
| After IPO | Alternating: Collection / hours | points per 100 h | One sector: Collection / hours | points per 100 h | alternating / one |
|---|---|---|---|---|---|
| 2 | 2002 / 100 h | 2.01 | 2002 / 99 h | 2.01 | 100% |
| 4 | 4004 / 197 h | 2.04 | 2004 / 196 h | 1.02 | 199% |
| 6 | 4006 / 295 h | 1.36 | 2006 / 294 h | 0.68 | 199% |

### 3. Task-bot against a dedicated human and a heavy human, same career (alternating sectors, hunting): stamps and Collection
Two metrics. **Collection total** is the doc's own (the board ranks Collection, CUSTOMIZE 1.6 = CUST:75; mark CUST:122 'the task-bot never above a dedicated human'). **Collection per stamp-clock hour** (Collection / the median stamp-clock hours of one IPO) is INVENTED by this sim, not in any doc. 'Gold or better, loops 1-3' counts every loop after the first (as the first version of this table did), which in an alternating career includes the first company of the other sector, a loop that is not a replay and can never be Gold; 'real replays' counts only the loops in a sector already finished (here IPO 3 and IPO 4). **heavy** = 5 h a day (the 3 h/day rule applies to it, a bot is not needed).
| Player | stamp-clock hours per IPO (median) | Platinum % of loops 1-3 | Gold or better %, loops 1-3 | Gold or better %, real replays | Collection after 4 IPOs, median (p10 to p90) | days to the 4th IPO | Collection per stamp-clock hour (INVENTED metric) |
|---|---|---|---|---|---|---|---|
| dedicated human, fast, hunting (2 h a day) | 48.5 | 0 | 54 | 81 (32 replays) | 4004 (2004 to 4004) | 103 | 82.6 |
| heavy human, fast, hunting (5 h a day) | 46.2 | 0 | 67 | 100 (32 replays) | 4004 (4004 to 4004) | 61 | 86.6 |
| task-bot, 24/7, hunting | 45.1 | 0 | 67 | 100 (8 replays) | 4004 (4004 to 4004) | 43 | 88.8 |
| FIX: stamp clock = raw engaged hours: dedicated human | 48.5 | 0 | 54 | 81 (32 replays) | 4004 (2004 to 4004) | 103 | 82.6 |
| FIX: stamp clock = raw engaged hours: heavy human | 71.9 | 0 | 0 | 0 (32 replays) | 2004 (2004 to 2004) | 61 | 27.9 |
| FIX: stamp clock = raw engaged hours: task-bot | 263.9 | 0 | 0 | 0 (8 replays) | 2004 (2004 to 2004) | 43 | 7.6 |

**Result.** New sector against replay: the hours differ by at most 0.4% (mark 10%): PASS. Points per hour, new sectors against replays: within 99% (FAIL; the replays only count when a better tier is reached). **The doc's own metric (Collection total):** the bot's median is 4004 against the dedicated human's 4004, so the bot is equal to the human (mark: never above): PASS (a tie at the median; per seed 4004 (4004 to 4004) against 4004 (2004 to 4004)). **The invented metric (Collection per stamp-clock hour):** the bot is +7.5% against the dedicated human (88.8 against 82.6), and the heavy human (5 h a day, no bot) is +4.9% (86.6): a human gets part of the same edge, and it grows with the hours played over the 3 h a day the rule counts at full value (2 h a day: 0 by definition, 5 h: +4.9%, 24 h: +7.5%), so the cause is playing more than 3 h a day, not being a bot (the heavy human gets 65% of the bot's edge, not all of it). Why: the 3 h/day rule weights only the valuation, never Cash, so anyone who plays more than 3 h a day has bought everything long before the weighted hours run out, and each weighted hour pays more. With the stamp clock counting raw engaged hours the bot's Platinum / Gold are 0% / 0% (real replays 0%), the heavy human's 0% / 0% (real replays 0%) and the dedicated human's 0% / 54% (real replays 81%; the dedicated human plays 2 h a day, so nothing changes for them): the fix takes tiers from every player who plays more than 3 h a day, bot or human; per day the bot is 2.4x faster, which LONG_GAME section 2 already accepts.


### S8. Funding rounds: the table is internally sound but priced wrong from Series C+D on; a player takes the maximum unless a pass or the stake stops them

**What the sim confirms.**
- The doc's basis-point tables are **reproduced by the formula** (to within 1-8 bp at Series B, Series C+D and Pre-IPO, because the sim's 59.9 h loop is not LONG_GAME's 59.8 h; Seed and Series A and all of today's table exactly), and **no choice is dominated at any stage** for LONG_GAME's 7 stages and for today's 5 (0 < S < M-S < L-M everywhere).
- Of the 1,024 LONG sequences, **4 lose Platinum on stake** (all four are Large in Series A, B, C+D and Pre-IPO); of today's 64, none. The cap of 4,000 bp never binds (largest total 3,042 and 1,999), and Gold's 55% can never fail, so only the 70% line is a real limit.
- **Round Cash never reaches the valuation:** the engine asserts, on every raise in both the long-game model and today's economy, that valuation, lifetime and earnings are unchanged.
- **Large every round saves 5.0% of IPO 1** in Software and 5.6% in Gaming (mark: at most 15%: PASS); FUNDING's upper bound (12.18% printed, 12.1% recomputed) is 2.5x the Software figure and 2.2x the Gaming one.
- **Converter and alt-fed gain "< 3% in loop 2" (FUND:107): PASS on one reading, 0.2 points over on the other.** Every one of the 97 items is already owned at each IPO in every case (the threshold is 1.5 x the price of everything), so round Cash has nothing kept left to buy: the converter cannot gain. The alt-fed player: **(A) what the alt adds over a plain player: -0.1 points: PASS**; **(B) the alt-fed player's absolute gain from rounds: 3.2%: not under 3, FAIL by 0.2 point** (a plain player gets 3.3%, so the 3.2% is what rounds give anyone in loop 2, not an alt exploit). The doc's wording does not say which gain it means.
- **Raising the last open round late:** the Pre-IPO round saves 0.60% when raised at once and **0.00% from halfway on**, for the same 1,909 bp: a late raise is all cost, skipping beats it: PASS.

**What fails or needs a decision.**
1. **FUNDING 3's claim "the price per hour saved is the same at every stage" is false (FAIL).** Measured, a Large round costs 1.7 / 2.3 / 2.8 % of Shares per 1% of loop time at Series A / B / C+D (close to the doc's 2.5) but **32% at Pre-IPO**: its Cash can only buy that rung's items, which pay back in tens of hours, so the round saves 0.6% of a loop where the table promises 7.6%. The Pre-IPO row (381 / 1,018 / 1,909 bp) is **6.7 / 9.3 / 12.7 times too dear** for Small / Medium / Large (the measured prices are 10.1 / 18.5 / 31.8 % of Shares per 1% of loop time against FUNDING's 1.5 / 2.0 / 2.5: the three figures 10 / 18 / 32 are prices, not multiples; an earlier draft of this sentence read them as multiples and said "10 to 30 times"), and it is the row that makes Large-every-round lose Platinum. Refitted to the measured savings (bp = P x saved% x 100) the Pre-IPO row is **56 / 109 / 150 bp** and Large every round costs 1,344 bp in all, so **the 70% stake line would never bite**. With the prices x2.3 (Large every round 3,095 bp) it bites again (5 sequences lose Platinum), at **Seed 8 / 22 / 48, Series A 117 / 313 / 571, Series B 200 / 509 / 919, Series C+D 258 / 673 / 1,212, Pre-IPO 130 / 252 / 345**; but that refit **fails dominance at Pre-IPO** (the measured savings flatten: 0.38 / 0.55 / 0.60%). The owner has to choose: keep the doc's table (Pre-IPO is a trap: 19% of Shares for 0.6% of a loop, which keeps the stake rule meaningful but teaches players to skip the last round), or the x2.3 table with a Pre-IPO row set by hand to stay convex.
2. **Is the maximum always best? Yes, for speed.** Large wins in 6 of 7 profiles even when Shares are valued (+3.0% against +2.4% for Medium at IPO 3), because the Shares it costs only delay a +25% perk. The exceptions: the **2x Cash owner** (Small +0.1%, Large -0.4%: the round Cash is worth less to them), and a player with the shop complete who protects Platinum (Medium; best per stage then: Large in Seed to C+D and Small at Pre-IPO, 1,514 bp). Mark "no one choice best for every profile": PASS, but because of one pass and the stake rule. **Which curve makes the choice real?** Multiplying all prices does not, beyond what the cap allows: at x2 the cap of 4,000 bp locks Large, and the speed-valuing regular and casual player only differ at x5. The stake minimum is what makes the choice real.
3. **Same round, same hours in both sectors (marginal).** The hours a round saves differ by 14-15% between Software and Gaming (Hit), 23-28% with Solid and Flop, as a ratio of the saved hours; in absolute terms it is 0.3 hours, 0.7 points of a loop for Large every round. Read as a ratio this fails the 5% mark; as a share of the loop it is under one point and **one `HoursShare` table serves both sectors**. FUNDING open question 2: keep one table.
4. **Dilution rounding is real but small.** Today's economy: with the nearest-Share carry the 10-IPO Shares are 512 / 474 / 427 (Small / Medium / Large) against 507 / 469 / 424 with a plain floor, so the carry returns 3-6 Shares (1%), and Large costs 20% of the Shares. At today's scale rounds change nothing measurable in time (the Cash is minutes of Income).
5. **Speed against tier (section F), under three Platinum rules.** The first version tested this only under a relaxed rule (1.0 T, ratio 1.10), not the doc's (0.8 T, ratio 1.25): it is now run under all three, for a dedicated fast hunter with the shop complete. **Under the doc's rule nobody has Platinum (0% on time in every policy), so the stake minimum has nothing to price: vacuous.** Under the S6 fix (1.0 T, ratio 1.20): no round 17% on time, Small 19% / 19% kept, Medium 25% / 25%, **Large every round 25% on time and 0% kept**. Under the relaxed rule (1.0 T, ratio 1.10): no round 25%, Small 33% / 33%, Medium 33% / 33%, **Large every round 42% on time and 0% kept**. (The first version's sentence "0% kept against 100% on time" was wrong: Large every round was on time for 42% of runs, not 100%, and the loss is 42 points of Platinum.) So Large every round makes the time target reachable more often but loses every Platinum it earns, and Small and Medium keep theirs: the minimum prices Large-every-round and takes Platinum from nobody who raises Medium or less (PASS where Platinum exists), but the 4 sequences that lose Platinum are all Large in the last four stages, so "most runs" are untouched only because most players do not take them.
6. **Ten loops (section G).** Large every round is fastest at IPO 1-3 (-5%, -2.5%, -1.3%) but by IPO 5 it is 1% slower than no round (52.5 against 51.9 h) because it pays 30% fewer Shares (296 against 425 over ten IPOs) and completes the speed perk one IPO later (7 against 6).

**Which tier rule each mark used.** The doc's rules are Gold 1.0 T, ratio 1, stake 55%; Platinum 0.8 T, ratio 1.25, stake 70%. S6's Gold and Platinum marks and S7's tiers used exactly those. S8's "4 of 1,024 sequences lose Platinum on stake" is stake arithmetic (D over 3,000 bp) and does not depend on any time or ratio rule. **S8's stake-against-speed mark (table F, item 5 above) was first measured only under the relaxed Platinum rule 1.0 T / ratio 1.10, not the doc's; it is now reported under the doc's rule, the S6 fix 1.0 T / 1.20 and the relaxed rule.** Every sentence of the S8 result block is computed from the tables above it (an earlier version hard-coded several of them, one of which, "0% kept against 100% on time", contradicted table F).

**Assumptions** are in section 5 (policies, "shop complete", best-per-stage search, the Pre-IPO test).

## S8. Funding rounds: round size, speed against Shares and against the stamp tier (docs/FUNDING_ROUNDS_PROPOSAL.md 1-6)
### A. The basis-point tables, recomputed from FUNDING 3's formula, and the dominance check

**LONG_GAME's 7 stages (5 rounds).** Cell = bp Small / Medium / Large: recomputed (doc).
| Stage | recomputed (doc) | Large: Cash as % of the gap to the next stage | Large: loop time it is worth (upper bound) | 0 < S < M-S < L-M ? |
|---|---|---|---|---|
| Seed | 3 / 8 / 15 (3 / 8 / 15) | 0.94% | 0.062% | yes |
| Series A | 34 / 91 / 170 (34 / 91 / 170) | 6.29% | 0.684% | yes |
| Series B | 73 / 196 / 368 (73 / 195 / 366) | 9.77% | 1.473% | yes |
| Series C+D | 116 / 309 / 580 (116 / 310 / 582) | 5.83% | 2.323% | yes |
| Pre-IPO | 380 / 1014 / 1901 (381 / 1018 / 1909) | 30.33% | 7.607% | yes |

All 1024 sequences of (none, Small, Medium, Large) over the rounds, doc table: **4 lose Platinum on stake (D over 3,000 bp)**, 0 lose Gold (over 4,500), 0 pass the 4,000 cap; the largest total is 3042 bp. Dominance (each step up costs strictly more per unit of Cash): holds at every stage.

**today's 5 stages (3 rounds).** Cell = bp Small / Medium / Large: recomputed (doc).
| Stage | recomputed (doc) | Large: Cash as % of the gap to the next stage | Large: loop time it is worth (upper bound) | 0 < S < M-S < L-M ? |
|---|---|---|---|---|
| Seed | 100 / 266 / 500 (100 / 266 / 500) | 12.00% | 2.000% | yes |
| Series A | 46 / 122 / 230 (46 / 122 / 230) | 11.05% | 0.921% | yes |
| Series B | 253 / 677 / 1269 (253 / 677 / 1269) | 12.19% | 5.078% | yes |

All 64 sequences of (none, Small, Medium, Large) over the rounds, doc table: **0 lose Platinum on stake (D over 3,000 bp)**, 0 lose Gold (over 4,500), 0 pass the 4,000 cap; the largest total is 1999 bp. Dominance (each step up costs strictly more per unit of Cash): holds at every stage.

### B. Hours saved by each single round (LONG ladder, regular typical, 10 seeds, same random streams, the shop is complete so Shares are worth nothing)
| Stage | Choice | Cash | dilution bp | hours saved, % of the loop (median, p10 to p90) | upper bound (the table's u) | % of Shares paid per 1% of loop time saved | FUNDING's price P | measured price / P (above 1 = too dear) |
|---|---|---|---|---|---|---|---|---|
| Seed | Small | 19.71K | 3 | 0.02% (0.01% to 0.04%) | 0.02% | 1.2 | 1.5 | 0.8x |
| Seed | Medium | 39.42K | 8 | 0.05% (0.04% to 0.08%) | 0.04% | 1.6 | 2.0 | 0.8x |
| Seed | Large | 59.13K | 15 | 0.09% (0.06% to 0.10%) | 0.06% | 1.8 | 2.5 | 0.7x |
| Series A | Small | 649.71K | 34 | 0.34% (0.32% to 0.36%) | 0.23% | 1.0 | 1.5 | 0.7x |
| Series A | Medium | 1.30M | 91 | 0.68% (0.67% to 0.70%) | 0.46% | 1.3 | 2.0 | 0.7x |
| Series A | Large | 1.95M | 170 | 0.99% (0.96% to 1.00%) | 0.68% | 1.7 | 2.5 | 0.7x |
| Series B | Small | 3.75M | 73 | 0.58% (0.55% to 0.60%) | 0.49% | 1.3 | 1.5 | 0.8x |
| Series B | Medium | 7.50M | 195 | 1.11% (1.09% to 1.13%) | 0.98% | 1.8 | 2.0 | 0.9x |
| Series B | Large | 11.25M | 366 | 1.60% (1.56% to 1.61%) | 1.47% | 2.3 | 2.5 | 0.9x |
| Series C+D | Small | 15.25M | 116 | 0.75% (0.73% to 0.77%) | 0.77% | 1.5 | 1.5 | 1.0x |
| Series C+D | Medium | 30.51M | 310 | 1.47% (1.44% to 1.48%) | 1.55% | 2.1 | 2.0 | 1.1x |
| Series C+D | Large | 45.76M | 582 | 2.11% (2.09% to 2.12%) | 2.32% | 2.8 | 2.5 | 1.1x |
| Pre-IPO | Small | 93.73M | 381 | 0.38% (0.38% to 0.40%) | 2.54% | 10.1 | 1.5 | 6.7x |
| Pre-IPO | Medium | 187.47M | 1018 | 0.55% (0.53% to 0.56%) | 5.07% | 18.5 | 2.0 | 9.3x |
| Pre-IPO | Large | 281.20M | 1909 | 0.60% (0.59% to 0.61%) | 7.61% | 31.8 | 2.5 | 12.7x |

### C. Round policies over a whole loop, both sectors (regular typical, shop complete, 10 seeds): hours saved at IPO 1 and IPO 2
| Policy | total dilution bp | Software: IPO 1 saved | Software: IPO 2 saved | Gaming (Hit): IPO 1 saved | Gaming: IPO 2 saved | hours saved at IPO 1, Software vs Gaming (difference) |
|---|---|---|---|---|---|---|
| Small every round | 607 | 2.0% | 1.4% | 2.3% | 1.7% | 0.92 h vs 1.06 h (15.1%) |
| Medium every round | 1622 | 3.6% | 2.5% | 4.2% | 2.9% | 1.67 h vs 1.92 h (15.1%) |
| Large every round | 3042 | 5.0% | 3.4% | 5.6% | 3.9% | 2.27 h vs 2.59 h (14.2%) |

Large every round saves 5.0% of IPO 1 in Software and 5.6% in Gaming (FUNDING's upper bound is 12.18%, mark: at most 15%).
Gaming with the other launch policies saves the same hours as Software (Large every round) within Solid 22.6%, Flop 28.4%.

### D. Is the maximum always best? Engaged hours to IPO 3, the shop NOT complete (Shares buy the speed perk), per profile and policy (10 seeds; cell = hours saved against no round; the best cell is bold)
| Profile | Small | Medium | Large | best |
|---|---|---|---|---|
| regular typical | +1.46% | +2.42% | **+3.01%** | Large |
| dedicated typical | +1.45% | +2.48% | **+3.00%** | Large |
| casual typical | +1.42% | +2.41% | **+2.93%** | Large |
| regular fast | +1.40% | +2.42% | **+2.93%** | Large |
| regular slow | +1.33% | +2.24% | **+2.72%** | Large |
| regular, 2x Cash | **+0.11%** | -0.03% | -0.39% | Small |
| regular, Shareholder | +1.34% | +2.00% | **+2.19%** | Large |

The only Share sink in the model is the speed lump (154 Shares for +25% Income), so the Shares a round costs delay a +25% perk by only a few percent of a loop: the best policy is Small, Large in every profile.

**What curve makes the choice real?** The same table with every basis-point price multiplied (the 4,000 cap stays); cell = the best policy by hours to IPO 3 for a player who values Shares (shop not complete), for a player with the shop complete who protects Platinum (total dilution at most 3,000 bp), and for a casual player:
| price multiplier | total of Large every round | regular, Shares valued: best | regular, shop complete, Platinum protected: best | casual, Shares valued: best |
|---|---|---|---|---|
| x1 | 3042 bp | Large | Medium | Large |
| x2 | 6084 bp | Large | Small | Large |
| x3 | 9126 bp | Large | Small | Large |
| x5 | 15210 bp | Large | none | Medium |
| x8 | 24336 bp | Large | none | Large |

**Best per stage** (coordinate search over the 4^5 sequences, 2 passes; hours to IPO 3, 3 seeds):
- Shares valued, shop not complete: Seed Large, Series A Large, Series B Large, Series C+D Large, Pre-IPO skip (total dilution 1133 bp)
- shop complete, Platinum protected (D <= 3,000 bp): Seed Large, Series A Large, Series B Large, Series C+D Large, Pre-IPO Small (total dilution 1514 bp)

### E. The other marks
**Alt-fed and converter, loop 2** (regular typical, shop complete; the alt feeds 3 poach-ins per run, which do not carry over an IPO, as LONG_GAME R2):
| Case | IPO 1 hours | IPO 2 hours | items owned at the IPO (of 97) |
|---|---|---|---|
| no rounds, no alt | 45.7 | 42.5 | 97 |
| Large every round | 43.4 | 41.1 | 97 |
| alt-fed, no rounds | 42.6 | 40.8 | 97 |
| alt-fed + Large every round | 40.7 | 39.5 | 97 |

In loop 2 Large every round saves a plain player 3.3% and an alt-fed player 3.2%. FUNDING 6 says 'converter and alt-fed gain < 3% in loop 2' (FUND:107), which can be read two ways: (A) what the alt adds over a plain player: -0.1 points: PASS; (B) the alt-fed player's absolute gain from rounds: 3.2%: FAIL by 0.2 point (a plain player gets 3.3% too, so it is not an alt exploit). The converter cannot gain either: every one of the 97 items is already owned at the IPO in every case (the IPO threshold is 1.5 x the price of everything), so round Cash has no kept employee left to buy. Not modeled: eggs and HR levels.

**Raising the last open round, late** (Pre-IPO round, Large, raised this far through the stage; regular typical, shop complete):
| Raised at | hours saved, % of the loop | dilution bp | bp per 1% of time saved |
|---|---|---|---|
| at once | 0.60% | 1909 | 3179 |
| 50% of the way | 0.00% | 1909 | 1909000000 |
| 90% of the way | 0.00% | 1909 | 1909000000 |
| 99% of the way | 0.00% | 1909 | 1909000000 |

### F. Speed against the stamp tier lost on stake (dedicated, fast, hunting for Platinum; shop complete; replays IPO 2-4; population 12)
Three Platinum rules, because the doc's gives Platinum to nobody (S6): **the doc's 0.8 T and ratio 1.25**, **the S6 fix 1.0 T and ratio 1.20**, and **the relaxed 1.0 T and ratio 1.10** (the only rule the first version of this table used; its marks were measured under it, not under the doc's). Stake at least 70% for Platinum in every rule; Gold: 1.0 T, stake 55%. T is refitted for a player whose shop is complete (Medium raise, the +25% speed perk from the start): 44.5, 41.4, 43.5, 45.5 h.
| Platinum rule | Policy | total dilution bp | hours per IPO (stamp clock) | Platinum on time and ratio % | Platinum kept after the stake rule % | Gold or better % |
|---|---|---|---|---|---|---|
| the doc: 0.8 T, ratio 1.25 | no round | 0 | 42.6 | 0 | 0 | 67 |
| the doc: 0.8 T, ratio 1.25 | Small every round | 607 | 42.0 | 0 | 0 | 67 |
| the doc: 0.8 T, ratio 1.25 | Medium every round | 1622 | 41.6 | 0 | 0 | 75 |
| the doc: 0.8 T, ratio 1.25 | Large every round | 3042 | 41.2 | 0 | 0 | 75 |
| S6 fix: 1.0 T, ratio 1.20 | no round | 0 | 43.7 | 17 | 17 | 17 |
| S6 fix: 1.0 T, ratio 1.20 | Small every round | 607 | 43.5 | 19 | 19 | 19 |
| S6 fix: 1.0 T, ratio 1.20 | Medium every round | 1622 | 43.5 | 25 | 25 | 25 |
| S6 fix: 1.0 T, ratio 1.20 | Large every round | 3042 | 43.5 | 25 | 0 | 25 |
| relaxed: 1.0 T, ratio 1.10 | no round | 0 | 43.5 | 25 | 25 | 25 |
| relaxed: 1.0 T, ratio 1.10 | Small every round | 607 | 43.4 | 33 | 33 | 33 |
| relaxed: 1.0 T, ratio 1.10 | Medium every round | 1622 | 43.0 | 33 | 33 | 33 |
| relaxed: 1.0 T, ratio 1.10 | Large every round | 3042 | 42.7 | 42 | 0 | 42 |

### I. The table refitted to the measured savings (bp = P x measured % of the loop saved x 100; P = 1.5 / 2.0 / 2.5, and the same x2.3 so that Large every round again costs about 3,000 bp)
| Stage | measured saved %: Small / Medium / Large | fitted bp at P | fitted bp at 2.3 P | the doc's bp |
|---|---|---|---|---|
| Seed | 0.02 / 0.05 / 0.09 | 3 / 9 / 21 | 8 / 22 / 48 | 3 / 8 / 15 |
| Series A | 0.34 / 0.68 / 0.99 | 51 / 136 / 248 | 117 / 313 / 571 | 34 / 91 / 170 |
| Series B | 0.58 / 1.11 / 1.60 | 87 / 221 / 399 | 200 / 509 / 919 | 73 / 195 / 366 |
| Series C+D | 0.75 / 1.47 / 2.11 | 112 / 293 / 526 | 258 / 673 / 1212 | 116 / 310 / 582 |
| Pre-IPO | 0.38 / 0.55 / 0.60 | 56 / 109 / 150 | 130 / 252 / 345 | 381 / 1018 / 1909 |
- fit at P: Small / Medium / Large every round cost 309 / 768 / 1344 bp; of 1024 sequences 0 lose Platinum on stake (D over 3,000) and 0 pass the 4,000 cap; dominance FAILS.
- fit at 2.3 P: Small / Medium / Large every round cost 713 / 1769 / 3095 bp; of 1024 sequences 5 lose Platinum on stake (D over 3,000) and 0 pass the 4,000 cap; dominance FAILS.

### G. Ten loops (regular typical, the shop not complete, 5 seeds): hours of each IPO, Shares, and when the speed lump (154 Shares) is complete
| Policy | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Shares paid, 10 IPOs | IPO at which the lump is complete |
|---|---|---|---|---|---|---|---|
| no round | 57.0 | 51.5 | 52.0 | 51.9 | 62.4 | 425 | 6 |
| Small every round | 55.9 | 50.8 | 51.6 | 51.5 | 61.5 | 399 | 6 |
| Medium every round | 54.9 | 50.4 | 51.3 | 51.8 | 60.7 | 356 | 6 |
| Large every round | 54.2 | 50.2 | 51.3 | 52.5 | 60.2 | 296 | 7 |

### H. Today's 5 stages (the Player model: 3 rounds, real IpoConfig numbers; online minutes of each IPO's run, Shares; median of 40 runs, 60 days)
The table's Cash is tiny next to a minute of today's Income, so rounds there are a smoke test (the runs are not paired: egg rolls differ). Shares paid with the nearest-Share carry (FUNDING 3) against a plain floor.
| Player | Policy | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Shares over 10 IPOs, with carry | plain floor |
|---|---|---|---|---|---|---|---|---|
| active | none | 12 min | 8 min | 15 min | 20 min | 2.4 h | 533 | 533 |
| active | Small | 12 min | 8 min | 15 min | 20 min | 2.4 h | 512 | 507 |
| active | Medium | 11 min | 9 min | 15 min | 20 min | 2.6 h | 474 | 469 |
| active | Large | 11 min | 9 min | 15 min | 20 min | 2.4 h | 427 | 424 |
| casual30 | none | 12 min | 10 min | 17 min | 12 min | 9.6 h | 500 | 500 |
| casual30 | Small | 12 min | 11 min | 17 min | 16 min | 9.6 h | 486 | 480 |
| casual30 | Medium | 11 min | 11 min | 18 min | 15 min | 9.6 h | 446 | 440 |
| casual30 | Large | 11 min | 10 min | 18 min | 29 min | 9.6 h | 399 | 396 |

**Result.**
- No choice is dominated at any stage, for LONG_GAME's 7 stages and today's 5: PASS on the doc's table (0 < S < M-S < L-M at every stage). A table refitted to the measured savings FAILS at Pre-IPO, where the measured savings flatten (0.38 / 0.55 / 0.60%) and Large costs less per extra Cash than Medium. 4 of 1024 LONG sequences lose Platinum on stake and 0 of 64 of today's; the cap never binds (largest total 3042 bp and 1999 bp against 4000), so only the 70% line bites. The cap is not redundant only as a safety net.
- **The price is not the same at every stage (FUNDING 3 says it is): FAIL.** Measured, a Large round pays 2.3% of Shares per 1% of loop time at Series B and 32% at Pre-IPO, against FUNDING's 2.5 (that is 12.7 times too dear for Large; the Pre-IPO row as a whole is 6.7 / 9.3 / 12.7 times too dear for Small / Medium / Large, and the prices themselves are 10.1 / 18.5 / 31.8 against 1.5 / 2.0 / 2.5): from Series C+D on, buying Cash is a poor deal, and at Pre-IPO nearly a pure loss, because the Cash can only buy the current rung's items, which pay back in tens of hours. Seed to Series B (0.1-1.6% of a loop for a Large round) are close to the doc's price.
- Large every round saves at most 5.6% of a loop (mark: at most 15%): PASS (FUNDING's upper bound, recomputed from its formula 12.1% (FUNDING prints 12.18%), is 2.5x the Software figure (5.0%) and 2.2x the Gaming one (5.6%): the Pre-IPO row is 7.6% in the table and 0.6% measured).
- Is the maximum always best? For a player who values speed, yes: Large is best in 6 of 7 profiles even with Shares valued (+3.0% against +2.4% for Medium at IPO 3 for the regular typical player). Exceptions: regular, 2x Cash: best Small (Small +0.1%, Medium -0.0%, Large -0.4%). Mark 'no one choice best for every profile': PASS, but only because of the profile(s) named. With the shop complete and Platinum protected, the best is Medium at the doc's prices. Scaling prices only helps up to the cap: at x5 the casual and the regular player first differ.
- The same round saves hours within 28% between Software and Gaming in relative terms (mark: 5%): FAIL by the letter (Hit 14-15%, Solid 23%, Flop 28%), but for Large every round it is 0.3 hours, 0.7 points of a loop; the Gaming launch cycle does not change the table, one `HoursShare` table is enough.
- Converter and alt-fed gain < 3% in loop 2 (FUND:107), two readings: (A) the alt-fed player's gain over a plain player is -0.1 points: PASS; (B) the alt-fed player's absolute gain from rounds is 3.2%: FAIL by 0.2 point (a plain player gets 3.3%). Converter: nothing to convert (all 97 items are owned at the IPO in every case; eggs and HR are not modeled).
- Raising the last open round late: 0.6% saved at once, 0.0% at 50% of the way and 0.0% at 90%, for the same 1909 bp: a late raise is a pure loss, skipping beats it: PASS.
- Stake against speed (table F; the stake mark was measured under three Platinum rules, the first version only under the relaxed one): under the doc: 0.8 T, ratio 1.25: no round 0% on time, Small 0% on time / 0% kept, Medium 0% / 0%, Large every round 0% on time and 0% kept after the stake rule; under S6 fix: 1.0 T, ratio 1.20: no round 17% on time, Small 19% on time / 19% kept, Medium 25% / 25%, Large every round 25% on time and 0% kept after the stake rule; under relaxed: 1.0 T, ratio 1.10: no round 25% on time, Small 33% on time / 33% kept, Medium 33% / 33%, Large every round 42% on time and 0% kept after the stake rule. The minimum prices Large-every-round (Platinum lost where it was won on time) without taking Platinum from the Small and Medium raisers, on the doc's table; under the doc's own Platinum rule nobody has Platinum to lose, so the mark is vacuous there. A table fitted to the measured savings never reaches 3,000 bp (fit at P: 1344 bp for Large every round), so the 70% line would never bite; at 2.3 P it does (3095 bp).


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


## 4. The placeholder numbers that must change, and to what

| Where | Now | Change to | Why (sim) |
|---|---|---|---|
| SECTORS 2.4 Gaming upgrade Incomes | "fitted base 0.77" | upgrade factor per rung **0.72 / 0.66 / 0.65 / 0.59 / 0.61 / 0.41** (0.74-0.83 of Software's *total* base, so 0.77 is right as a total); with fix B **0.81 / 0.78 / 0.78 / 0.73 / 0.75 / 0.61** | S3 |
| SECTORS 2.4 peaks, cap, catalog | 0.15 / 0.35 / 0.6 / 0.8, cap 0.8, catalog 10% | **x0.6**: 0.09 / 0.21 / 0.36 / 0.48, cap 0.48, catalog 6% (optional: halves the skill spread of S3; policies matter less) | S3, S9 |
| SECTORS 2.4 away bank | 10% of Gaming's base | 10% of the base the same purchases give in Software (`SectorGaming` data) | S3 (check-in +26% -> +7-12%) |
| SECTORS 2.4 per-title bound `k` | unset | **k = 0.4** x build seconds x base Income (or half-lives 20 / 40 / 60 / 80 / 120 min) | S9 (spam +1.7% -> +0.4% / 0.0%) |
| SECTORS 2.10 Smash | "5% faster, 54 h" | Smash with 'every update' is slower than Hit (58.5 h against 57.5 h), with 'update under half' it is 1.1% faster; Hit 57.5, Solid 61.8, Flop 65.5, never 71.6 h. To make Smash matter: cap above 0.8 | S9 |
| SECTORS 2.10 titles to IPO 1 | about 40 | **49** (4 / 7 / 8 / 7 / 14 / 9) | S3 |
| SECTORS 2.2 cycle | decisions at Pitch, Playtest, Launch | add a **checkpoint verb every 12 engaged minutes** while a title is in development | S10 |
| CUSTOMIZE 1.5 Platinum | 0.8 T and ratio 1.25 | **1.1 T and ratio 1.25** (typical 29%, fast 69% of dedicated hunters; 1.0 T / 1.20 gives typical 0%, fast 25%, so it only helps fast players) | S6 |
| CUSTOMIZE 1.5 pass shrink | 15% (Cash pass only) | **6%** for the 2x Cash pass, **6%** for the Shareholder pass | S6 |
| CUSTOMIZE 1.5 T | 57 / 51.5 / 52 h | **55.5 / 50.4 / 51.2 / 51.6 h** with a typical raise (Medium) and the seed | S6 |
| CUSTOMIZE 1.5 stamp clock | weighted like the valuation | optional: **raw engaged hours** (not needed for the doc's mark: the bot ties the human on Collection total; it takes tiers from every player over 3 h a day) | S7 |
| CUSTOMIZE 5.1 seed | s 10%, c 25% | keep c = 25%; `s` can go (cap binds in 100% of runs) | S1 |
| CUSTOMIZE 5.2 bonus | +1.5 / 0.5 / 0.5, cap 10 | keep (worth 3.4% at most for a no-pass player) | S2 |
| FUNDING 3 prices | 381 / 1,018 / 1,909 bp at Pre-IPO; "the price per hour is the same everywhere" | the claim is false; Pre-IPO row **56 / 109 / 150** on the measured savings, or the whole table x2.3 (Seed 8 / 22 / 48, A 117 / 313 / 571, B 200 / 509 / 919, C+D 258 / 673 / 1,212, Pre-IPO 130 / 252 / 345) with the Pre-IPO row hand-set to stay convex | S8 |
| FUNDING 3 upper bound | Large every round "at most 12.18% of a loop" | measured **5.0% / 5.6%** | S8 |
| FUNDING 9 question 2 | one `HoursShare` table or two | one table (0.6 points of a loop apart) | S8 |


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

**S6 / S7.** *T* is **measured**, not taken from LONG_GAME: the median stamp-clock hours of the regular typical player per loop with a typical raise (Medium at every round) and the placeholder seed (CUSTOMIZE open question 1). A *profile* is a population: each seed's task skill is x(1 +- 20%) (my number; without it every player of a profile is the same person). *Fast* = expert at tasks, *slow* = the task bonus x0.5 (LG:12's own sensitivity row), *dedicated* = 2 h a day. A *replay* = IPO 2, 3, 4 of the same sector. *Hunting* = go public only when the ratio has reached 1.25 (or Platinum is out of time); *ready* = go public at once. The pass-share shrink uses the whole run with the pass. S7 reads "within 10%" as hours (and, separately, as points per hour: that second reading is this sim's own), and "the bot never above a dedicated human" as the Collection total of CUST:75 (the doc's metric); "Collection per stamp-clock hour" is invented and reported separately (per day the bot is faster by design, LONG_GAME section 2).

**S8.** *Policies* none / Small / Medium / Large every round; *best-per-stage* = a coordinate search (two passes, last stage first) over the 4^5 choices for the fewest hours to IPO 3, once with Shares valued (the speed perk) and once with the shop complete and total dilution at most 3,000 bp. *Shop complete* = the +25% speed lump from the first loop and Shares worth nothing; *Shares valued* = the lump (154 Shares, LONG_GAME's own estimate) is the only sink, so Shares are worth little in this model. A raised round is Cash only (asserted: valuation, lifetime and best are unchanged). The converter is checked by counting what is still unowned at the IPO; the alt feeds 3 poach-ins per run (R2) that do not carry over. "Raising the last open round" = the Pre-IPO round raised at 0 / 50 / 90 / 99% of its stage. *Today's 5 stages* use the Player model (real IpoConfig, egg rolls; runs are not paired).

**S10.** A moment = a **timed** event (a purchase, a milestone, a board request, and in Gaming Pitch / Playtest / content complete / Launch / Update). Untimed content is not in the sim, so Software's non-C+D gaps are upper bounds.

**Everything.** Same random stream for the same seed and profile, so two options differ only by what they change; steps of 20 s; the 3 h/day rule and the 08:00 UTC day as in `--long`. Seeds per cell: S1 and S2 40, S3 40 (check-in 10), S4 and S5 10 (24/7 runs are long), S6 population 16, S7 8, S8 10 (5 for ten loops), S9 20; S10 is one deterministic reference run.

## 6. Output of the default run and of `--long`: unchanged

`python tools/economy_sim.py > after.txt` and `python tools/economy_sim.py --long > after_long.txt` were compared byte for byte (`cmp`) with the output of the unmodified script on `main` `e3c9e67`: **identical**, before the first commit and again before the last. The only edit to existing code is one line in `run()` (`player_cls`, default `Player`) so that S8 can run today's economy with rounds; with the default it builds the same object. Everything else is new code after `report_long` and in `main()`'s argument list.

**Branch note.** The sims were first committed to `sims-two-sectors`; while this work was in progress two commits from another session (`95e30cc`, a CONTRIBUTING.md claim, and `c84a278`, `CompanyConfig.lua`, `SectorConfig.lua` and `tools/daily_test.py`) landed on that branch by accident. They did not touch `tools/economy_sim.py`, `docs/SIMS_RESULTS.md` or anything these sims read (`git diff f67ee5c sims-two-sectors -- tools/economy_sim.py docs/SIMS_RESULTS.md` is empty), so no number here depends on them. To keep this pull request to its own files, the work lives on **`sims-two-sectors-clean`**, branched from `origin/main`, with my claim commit cherry-picked; `sims-two-sectors` was not reset, rebased or force-pushed.

## 7. What was NOT modeled

- Egg rolls, hatch timers and poaching in the long-game ladder (the hire is the planned creature, as in `--long`), HR levels, eggs and the converter beyond "nothing is left to buy"; real poaching between people; D9 fixed-order hires.
- Fun and Polish as separate meters, the Playtest card's effect, the Trailer's three beats, the trend schedule and genres (trend is always matched), game names, reviews; real Gaming task rows (their arrival rates are not in the doc).
- Any perk other than the one speed lump, offline pay above the away bank, the daily calendar, weekly events, Cash packs.
- Mixed populations (a player who changes skill, schedule or pass during a run), passes bought mid-run (pass share is 0 or 1), players who leave, fun, retention, and the social side of the leaderboard (Collection is computed per player, not ranked).
- Fintech and Biotech; the Studio UI limits; the real task bonus (f is the model's Monte Carlo; LONG_GAME's gate G1 measures it).
- The real server's rules about shared saves between Studio and live.
