# Economy report: Build your Startup!

Made with `tools/economy_sim.py` (Python, standard library only). Run it yourself:

```
python tools/economy_sim.py --runs 40
```

All game numbers are copied by hand into the CONFIG block at the top of the script, each with a comment saying which `.lua` file it came from. **If you change a game number, change it there too.** The simulator never changes the game.

> **IPO numbers are real**, read from `IpoConfig.lua` after the `ipo-retune` retuning pass. The simulator does **not** model IPO shop perks (Faster Recruiting, Extra Incubator, Extra Desk, Night Shift, Talent Scouts, Recruiter Network): every figure below assumes a player with no perks. A perk-buying player is estimated to be roughly 15-25% faster per IPO cycle.

## How the simulated player behaves

- Starts with 0 Cash and only the free Desk. Spends Cash greedily, cheapest payback first: next garage upgrade, then eggs. When Cash is plentiful it buys the egg with the best expected income.
- Keeps the best creatures when the team is full (replaces the weakest). Hatching needs the player online, because the real server only hatches for players who are in the game. The timer keeps running offline, but the creature is only claimed at the next login.
- Without Auto-Hatch the player takes 20 s to notice a hatched egg. With Auto-Hatch, 0 s.
- Offline pay is read from `TycoonCore.lua`: 50% of income (passes included), capped at 8 hours per login.
- Buys HR Department levels once everything else is bought (a Cash sink).

| Behaviour | Sessions |
|---|---|
| active | 3 per day, 20 min each (start, +5 h, +11 h) |
| casual | 1 per day, 10 min |
| idler | 1 minute per day, only to collect offline Cash and spend it |

The idler needs that one minute: nothing can be bought or hatched while away. "Offline gains only" with zero logins would earn nothing at all.

**Not modelled:** poaching, Instant Hatch, Cash packs, the IPO shop, events (M7). Daily rewards (M6) are modelled in section 7 only. The simulated player is a perfect, never-distracted optimiser, so real players will be slower. Results are the median of 40 random runs (days 1, 3 and 7 are days of the player's own clock, starting at their first login).

## 1. Summary table: base game, no passes

| Behaviour | First employee | All 6 upgrades | 3 slots | 5 slots (base max) | 8 slots | 10 slots | Cash/h day 1 | day 3 | day 7 | Income/s day 7 |
|---|---|---|---|---|---|---|---|---|---|---|
| active | 5 min | 7 min | 6 min | 7 min | n/a (needs pass) | impossible | 635K | 1.28M | 1.61M | 1.06K |
| casual | 5 min | 7 min | 6 min | 7 min | n/a (needs pass) | impossible | 130K | 185K | 365K | 584 |
| idler | 48 h | 24 h | 48 h | 3 d | n/a (needs pass) | impossible | 1.8K | 130K | 279K | 463 |

With the Extra Employee Slots pass (8 slots): active 5 slots 7 min and 8 slots 9 min; casual the same; idler 5 slots 3 d and 8 slots 4 d.

"10 slots" cannot happen: the cap is 5 base + 3 from the pass = 8.

## 2. What the passes change (day-7 Cash per hour, compared with no pass)

| Scenario | active | casual | idler | Speed to all 6 upgrades (active) |
|---|---|---|---|---|
| No pass | 1.61M (x1.00) | 365K (x1.00) | 279K (x1.00) | 7 min |
| 2x Cash (199 R$) | x1.99 | x2.14 | x2.06 | 4 min |
| VIP (249 R$) | x1.50 | x1.51 | x1.50 | 5 min |
| 2x Cash + VIP (x3) | x3.00 | x3.09 | x3.58 | 3 min |
| Extra Slots (149 R$) | x1.40 | x1.18 | x1.13 | 7 min |
| Luck Boost (49 R$ per 15 min, one per session) | x1.00 | x1.09 | x1.08 | 7 min |
| Auto-Hatch (199 R$) | x0.99 | x0.99 | x1.00 | 6 min |
| Everything + Luck | x4.33 | x3.76 | x4.23 | 3 min |

Without any pass the game is playable: all upgrades and a full team of 5 in 7 minutes, and a casual player is not locked out of anything. Passes make it faster, but no pass is needed to progress. The exception is "10 slots", which doesn't exist.

Day 1, 3 and 7 for each scenario are in the script output (`python tools/economy_sim.py`).

## 3. IPO rebirth (real `IpoConfig.lua` numbers, retuned on `ipo-retune`)

Stages: Seed 1,800, Series A 6,300, Series B 23,400, IPO-ready 81,000 valuation. Each IPO: income x(1 + 0.5 x IPOs^0.75) (diminishing returns per IPO, no stall) and the next run's stage thresholds x2.5. Employees, passes and the HR Department level are kept; Cash, garage upgrades and incubating eggs reset.

Session assumptions used by the simulator: active = 3 x 20-min sessions/day, casual = **one 10-min session/day**, idler = **one 1-min session/day** (collect-and-leave, a floor case, not a typical session). Real mobile sessions can run longer, so these are conservative (slower) estimates.

| Behaviour | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Multiplier at IPO 10 |
|---|---|---|---|---|---|---|
| active | 12 min | 5.0 h | 5.2 h | 24 h | 6.3 d | x3.81 |
| casual | 24 h | 24.2 h | 48 h | 4 d | 20 d | x3.81 |
| idler | 48 h | 3 d | 4 d | 6 d | 26 d | x3.81 |

**2-hour continuous active session (binge):** median 4 IPOs (range 4-5), or median 5 (range 4-5) with an estimated +25% perk speedup applied. Caps around IPO 5 even for an uninterrupted player, as intended.

**First IPO:** lands at ~10-15 min of active play (was 5+ hours with the placeholder numbers), carrying the mid-game as planned. Casual's first IPO lands at the "next day" bound (24h), not within their single 10-min session — a lower Seed threshold was tested but broke the 2h-binge cap (active players reaching IPO 6+), so Seed stayed at 1,800. No gap between consecutive IPOs 1-10 for active play exceeds 3 days.

To change: edit `IpoConfig.lua`, then update the `IPO_*` values in the CONFIG block of `tools/economy_sim.py` to match and re-run.

### 3b. Real IPO numbers in minutes of play, with Shares (`economy-sim-real-ipo`)

The IPO numbers in `tools/economy_sim.py` match `IpoConfig.lua` exactly (checked line by line after PR #9). New in the script: **Shares** (with and without the Shareholder pass), a **casual30** player and the **2-hour binge** as real behaviours, and every time below is **minutes really spent online** (not wall-clock), median of 20 runs. Perks are not modelled. Run `python tools/economy_sim.py --runs 40` and read section 6 of the output.

Players: **active** = 3 x 20 min/day. **casual30** = about 30% of a 16 h waking day, 4 x 72 min/day (this is a guess at "30% active"). **casual** = 1 x 10 min/day.

**1. First run, minutes online to reach each funding stage (same for every behaviour: the first session is continuous)**

| Seed | Series A | Series B | IPO-ready (IPO #1) |
|---|---|---|---|
| 4 min | 6 min | 7 min | 12 min (casual: 10 min of play, at the 2nd login, see note) |

**2. Online time to IPO #N and Shares earned there (no pass / Shareholder)**

| Player | IPO #1 | IPO #2 | IPO #3 | IPO #5 | IPO #10 | IPOs in 60 days |
|---|---|---|---|---|---|---|
| active, time online | 12 min | 20 min | 35 min | 60 min | 6.7 h | 13 |
| active, Shares | 10 / 20 | 39 / 78 | 10 / 20 | 20 / 42 | 10 / 20 | 190 / 384 total |
| casual30, time online | 12 min | 22 min | 40 min | 82 min | 19.2 h | 13 |
| casual30, Shares | 10 / 20 | 10 / 20 | 10 / 20 | 10 / 20 | 10 / 21 | 138 / 280 total |
| casual (10 min/day), time online | 10 min | 20 min | 20 min | 40 min | 3.3 h | 11 |
| casual, Shares | 62 / 125 | 10 / 20 | 40 / 80 | 22 / 44 | 10 / 20 | 240 / 486 total |

Note on Shares: the simulated player goes public the moment IPO-ready is reached, which gives exactly 10 Shares (20 with the pass). The bigger numbers (39, 62) are players who log in after hours away: the offline Cash is counted as valuation, so they arrive far above the threshold and Shares grow with the square root of that. This is how the real game works too.

### 3c. Shares grow with the IPO count, ratio capped at 4 (`ipo-shares-growth`)

Two small changes in `IpoConfig.sharesFor`, one commit each. Shares = `SharesPerIpo * (1 + 0.3 * IPOs done) * min(ratio, 4) ^ 0.5` (new `SharesGrowthPerIpo = 0.3`, `SharesRatioCap = 4`). The 1st IPO gives 10, the 2nd 13, the 11th 40; the cap means one IPO can never give more than 2x the base (waiting past 4x IPO-ready, for example offline Cash, adds nothing). `StageGrowthPerIpo` is unchanged. Old saves load as before: the formula only reads the saved IPO count, and a save without one counts as 0 IPOs. `tools/economy_sim.py` has `IPO_SHARES_GROWTH` and `IPO_SHARES_RATIO_CAP` to match. Run with `--runs 40`, section 6, median, 60 days.

**IPOs and online time to buy the whole shop (525 Shares)**

| Player | Before growth (about 10 Shares per IPO) | Growth, no cap: no pass / pass | Growth + cap 4: no pass | Growth + cap 4: Shareholder pass |
|---|---|---|---|---|
| active (3 x 20 min/day) | 53 IPOs | not in 60 d (472) / IPO #8, 3.0 h | not in 60 d: 13 IPOs, 435 Shares | IPO #9, 4.3 h online |
| casual30 (4 x 72 min/day) | 53 IPOs | not in 60 d (386) / IPO #11, 39.6 h | not in 60 d: 13 IPOs, 386 Shares | IPO #11, 39.6 h online |
| casual (10 min/day) | 53 IPOs | not in 60 d (484) / IPO #6, 50 min | not in 60 d: 11 IPOs, 373 Shares | IPO #9, 2.0 h online |

Without the pass nobody finishes the shop in 60 days. The sim stops at 60 days, so how many more IPOs they need is my estimate from the Shares per IPO: about 15-16 for active, about 16 for casual30 and about 15 for casual (not simulated). A player who always goes public exactly at IPO-ready needs 17 IPOs without the pass and 11 with it.

**Effect of the cap:** the casual player's IPO #1 drops from 62 to 20 Shares (40 with the pass instead of 125) and IPO #3 from 64 to 32. The active player's IPO #2 drops from 51 to 26. Casual30 does not change (it never overshoots 4x).

**Does the 10-min-a-day player with the pass still buy everything too fast?** Better, but yes, still a bit fast. It was 6 IPOs and 50 min online; it is now 9 IPOs and 2.0 h online, about the same as the active player with the pass (4.3 h). 2 hours at 10 minutes a day is about 12 days of logging in, so it is no longer a one-evening shop, but this player is faster than the casual30 player (39.6 h), which is backwards. Reason: a returning player's offline Cash is counted as valuation and clears the next threshold at once (IPO #3 lands 1 minute after IPO #2), so IPOs come from logins, not from play, and each one is worth up to 2x the base.

**Suggested next fix (applied in 3d below):** lower `SharesRatioCap` from 4 to 2 (max about 1.41x the base per IPO). Then waiting is worth little and the casual player is roughly in line with the others. If that is not enough, the root cause is the offline Cash clearing thresholds: lower the offline rate after IPO #5 (see section 5) or give a longer `CooldownSeconds` (60 s now, 30 min would stop two IPOs in one login). Change one thing at a time and re-run the sim.

### 3d. Final numbers: growth 0.8, ratio cap 2

`IpoConfig.sharesFor` is now: Shares = `SharesPerIpo * (1 + SharesGrowthPerIpo * IPOs done) * min(ratio, SharesRatioCap) ^ SharesExponent * (2 with the Shareholder pass)`, where ratio = valuation / IPO-ready valuation. Values: `SharesPerIpo = 10`, **`SharesGrowthPerIpo = 0.8`** (was 0.3), `SharesExponent = 0.5`, **`SharesRatioCap = 2`** (was 4, so one IPO pays at most 1.41x the base). The 1st IPO gives 10, the 2nd 18, the 11th 90. Stages, bonus and cooldown are unchanged, so IPO timing is unchanged (checked: first IPO 12 min online, IPO #10 at 6.6 h for active). The sim constants `IPO_SHARES_GROWTH` and `IPO_SHARES_RATIO_CAP` match. Reproduce with `python tools/economy_sim.py --ipo --runs 40 --days 365` (median of 40 seeds, 365 days, daily calendar off).

**Shares per IPO (no pass / Shareholder pass)**

| Player | IPO #1 | #2 | #3 | #5 | #10 |
|---|---|---|---|---|---|
| active (3 x 20 min/day) | 10 / 20 | 25 / 50 | 26 / 52 | 59 / 118 | 83 / 166 |
| casual30 (4 x 72 min/day) | 10 / 20 | 18 / 36 | 26 / 52 | 48 / 98 | 88 / 176 |
| casual (10 min/day) | 14 / 28 | 18 / 36 | 36 / 73 | 59 / 118 | 84 / 168 |

**Shop pace: the whole IPO shop (525 Shares, before D1; now 1,770, see 3e)**

| Player | No pass | Shareholder pass |
|---|---|---|
| active | IPO #10, 7.0 h online, **about 7 days** | IPO #7, 2.0 h online, **about 2 days** |
| casual30 | IPO #11, 39.6 h online, about 8 days | IPO #7, 4.8 h online, about 1 day |
| casual | IPO #10, 3.3 h online, about 20 days | IPO #7, 60 min online, about 6 days |

Days = online time divided by the player's daily play time (active 1 h/day, casual30 4.8 h/day, casual 10 min/day).

**What this does not tell you:** perk effects (FasterEggs, ExtraIncubator, ExtraSlot, OfflineCap, BaseLuck, CheaperPoach) are **not modeled**. Every figure assumes no perk is ever bought; real players buy perks as they go and will be faster, roughly 15-25% per IPO cycle (an estimate, not simulated).

**Decision (D1, built on `launch-decisions`, 2026-10-02):** the pass stays at 2x and the shop grew from 525 to 1,770 Shares. See section 3e. The old "very strong early, little to buy after week 1" problem is what 3e fixes.

### 3e. The 1,770-Share shop (D1)

`IpoConfig.Perks` now costs **1,770 Shares** in total (was 525). Only new levels were added, at the end of three perks: Faster Recruiting 6-7 (90, 140; hatch time up to -70%), Talent Scouts 6-8 (80, 120, 175; luck up to +80%) and Recruiter Network 6-10 (50, 75, 110, 165, 240; poach cost up to -50%). Extra Incubator, Extra Desk and Night Shift were **not** extended (more incubators, desks or offline hours would speed up every IPO), and every old level cost and effect is unchanged. `IPO_PERK_COSTS` in `tools/economy_sim.py` matches. Details, options and checks: docs/D1_SHOP_OPTIONS.md.

The stage numbers and the Shares formula are unchanged: `python tools/economy_sim.py --ipo --runs 40 --days 365` still gives the first IPO at 12 min online and IPO 10 at 6.6 h for active, and the rows of section 3d are identical. That is only because the sim does not model perks (`IPO_PERK_COSTS` is used for the shop total and nothing else). In the real game the new levels, Faster Recruiting 6-7 (hatch time, up to -70%) and Talent Scouts 6-8 (luck, up to +80%), speed up later runs for players who buy them, so later runs can be faster than the sim shows; by how much is not measured. Only the "whole shop" lines changed. Days are real days (wall clock), median of 40 seeds:

| Player | No pass | Shareholder pass |
|---|---|---|
| active (1 h/day) | not in 365 days (IPO 15, 1,063 Shares: 60%) | IPO #14, **125 days** (124.7 h online) |
| casual30 (4.8 h/day) | not in 365 days (1,031 Shares: 58%) | IPO #14, **96 days** (462 h online) |
| casual (10 min/day) | not in 365 days (961 Shares: 54%) | IPO #14, **309 days** (51.5 h online) |

For comparison, the 525-Share shop took 7 / 8 / 20 days without the pass and 2 / 1 / 6 with it (section 3d). Share of the 1,770 owned after 7 / 30 / 90 / 365 days, active: no pass 30 / 41 / 47 / 60%, pass 60 / 82 / 94 / 100%.

**The pass is exactly 2x Shares at any date** (it doesn't change when IPOs happen), but "days to finish" is not 2x apart: IPOs get about 2.3 times rarer each time, so doubling the Shares saves about 3 IPOs, and the last IPOs take 10-50 times longer than the early ones. A bigger shop makes that gap larger, not smaller; a real 2x in days would need Shares per IPO to grow geometrically (not done, see D1_SHOP_OPTIONS.md section 2). Also, in the sim `casual30` plays 4.8 h a day and `active` 1 h a day, so casual30 is the heavier player; the order that holds is {active, casual30} faster than casual.

**Perks are still not modeled.** Real players buy perks and are roughly 15-25% faster per IPO cycle, so real days are up to 20% fewer than the table (the 125 / 96 days still clear 4 weeks / 8 weeks). Sections 3b and 3c quote the 525-Share shop of their time and are kept as history.

**3. Running out of things to do.** The base game was finished in about 7 minutes. Now the first run is still 12 minutes, but the run after it is not finished: an active player needs about **1 hour online for 5 IPOs, 6.7 hours online for 10** and still has not bought the whole IPO shop (525 Shares at the time, now 1,770: see 3e) after 60 days (13 IPOs, 190 Shares; 384 with the pass, numbers from before the Shares growth). So yes, the IPO now carries the mid-game: there is something to do for weeks. The 2-hour binge ends at 4 IPOs (range 4-5), as intended. The honest caveat: the first hour is fast (IPO #1, #2, #3 at 12, 20 and 35 min), and after IPO #5 it slows down sharply.

**4. Casual (30% active):** same first 12 minutes, IPO #5 at 82 min online (about a day), IPO #10 at 19 h online (about 4 days at 4.8 h/day), 13 IPOs in 60 days. A once-a-day 10-minute player gets 11 IPOs in 60 days. Casual players are not locked out.

**5. Numbers that look off (suggestions only, `IpoConfig.lua` unchanged)**

| What | Problem | Suggested fix |
|---|---|---|
| Shares per IPO | **Done on `ipo-shares-growth`:** `sharesFor` now uses `SharesPerIpo * (1 + 0.8 * IPOs)` and cap 2 (first written as 0.3, see sections 3c and 3d). | Before: about 10 per IPO, so the whole shop (525) needed about 53 IPOs. |
| Late IPOs are gated by logins, not by play time | Active, casual and idler all get 10-13 IPOs in 30-60 days: employees are kept, so offline Cash alone (8 h at 50%) clears the next threshold. Extra play time buys little after IPO #5. | Fine for retention, but if you want playing to matter, raise `StageGrowthPerIpo` a little (2.5 to 3) or lower the offline rate after IPO #5. Try one change at a time. |
| Offline overshoot pays more Shares | A player who returns after hours can get 4-6x the Shares of one who plays through (39 vs 10, casual 62 vs 10 at IPO #1). | Done on `ipo-shares-growth` (cap 4, then cap 2 in section 3d). |
| Multiplier | x1.50 at IPO #1, x3.81 at #10, x4.22 at #12. Slow and diminishing, not a runaway. | OK as is. |
| First 35 minutes | IPO #1, #2 and #3 land at 12, 20 and 35 min. The second run is faster than the first (employees and the multiplier are kept). | OK; makes the loop clear early. If it feels too fast, only the Seed to Series B values need to grow. |
| Cooldown (60 s) | Not hit by the sim: the shortest gap between two IPOs is about 1 minute online for the 10-min casual (an offline-cash jump). Cooldown still protects against abuse. | OK. |

## 4. Ten findings

1. **The first employee arrives at minute 5, not minute 1.** The simulated player buys three upgrades first (they pay back faster than an egg), then the first Garage egg at about minute 3, and it hatches 60 s later. M5's "free egg and first employee within 60 seconds" is needed; today nothing in the first minutes points at eggs.
2. **The whole "build phase" lasts 7 minutes.** All six garage upgrades and a full team of 5 are done by then (active and casual alike). After that, the garage has nothing left to buy: only 183 Cash/s comes from upgrades in total.
3. **Day-1 players hit a wall at about hour 5.** An active player has bought every HR level (522,500 in total) by hour 5 and meets a first Legendary around hour 5; by day 7 the team income is 875/s, which is exactly the maximum for 5 slots (5 x 175). Cash/h flattens from day 3 (1.28M) to day 7 (1.61M). From then on Cash has nothing to buy. This is the biggest boredom risk in the base game, and IPO has to fix it (see finding 10).
4. **Prices are tiny compared with income, so Cash is not the limit; time is.** At about 700 Cash/s, a Unicorn egg (25,000) costs 36 seconds of income and a Startup egg (2,500) costs 4 seconds. What actually slows the player down is 3 incubators and the hatch timers (60 s, 5 min, 15 min). Active players first buy a Startup egg at minute 7 and a Unicorn egg at minute 18.
5. **2x Cash makes progress 2.0x faster and nothing else.** It doubles Cash/h and cuts "all upgrades" from 7 to 4 min. It is the clearest pass and fair: a free player still gets the same content. VIP adds 1.5x for 249 R$ against 2x for 199 R$, so on Cash alone VIP is the worse deal; it relies on the tag and the lounge to sell. The two stack to x3, so buying both is worth about 1.5x more than 2x alone.
6. **Luck Boost is weak and its text was misleading (text fixed: it now shows the real odds, "Legendary chance 8.0% -> 9.7% (Unicorn Egg)"; the balance is unchanged).** It said "2x rare employee chance", but because the odds are scaled back to 100%, a Unicorn egg's Legendary chance only goes from 8.0% to 9.7% (x1.2) and a Startup egg's from 1.0% to 1.6%. The effect on income is +35% for a Startup egg and +17% for a Unicorn egg for 15 minutes, and only +8% to +9% on day-7 Cash/h for casual players. Players who pay 49 R$ expecting double Legendaries will feel cheated.
7. **Auto-Hatch changes nothing in the numbers (x0.99 to x1.00).** It only saves clicks, and the server only auto-hatches while the player is online. It is a comfort pass at 199 R$. It does not help the "while I'm away" story at all.
8. **Extra Slots matters late, not early.** Base slots fill in 7 minutes, so the pass does nothing for the first day, then gives x1.40 for active players by day 7 (x1.13 for idlers, who don't even fill 5 slots for 3 days). It is the best long-term value, but players only feel it after the base slots are full.
9. **Idlers and the 8-hour cap.** An idler who logs in every 24 h is only paid for 8 of those 24 hours, at 50%: about 17% of what the startup earned. They reach all upgrades only after 24 h and their first employee after 48 h (an egg needs a login to hatch, and a 1-minute login is shorter than the 5 min Startup timer). Day 3 is when they first reach 130K Cash/h, versus 1.28M for an active player: 10x less for roughly 1/60 of the playtime. That is fair, but it will feel slow to someone who doesn't know that a second login after the egg timer would double their progress.
10. **IPO placeholder: the first stage is meaningless and later ones are OK.** With 10x stages starting at 50K, Seed arrives in 9 minutes for everyone who plays, so the stage just before the first real goal is invisible. The first IPO takes an active player about 2.5 days, a casual 8.5 days and an idler 10 days, which is a reasonable spread. A permanent x1.5 for the first IPO is meaningless against the cap of 875/s, though: the real fix for finding 3 is that IPO gives players something new to buy (more slots, higher-tier creatures), not only a multiplier.

## 5. Numbers to consider changing

| What | Now | Why | Suggestion |
|---|---|---|---|
| Egg prices (`CreatureConfig.Eggs`) | 250 / 2,500 / 25,000 | Cash is not a limit after minute 20 (finding 4). A Unicorn egg costs 36 s of income. | Raise Startup and Unicorn about 10x (25K and 250K), so they cost minutes of income, not seconds. Keep Garage at 250. |
| Garage upgrades (`TycoonCore.lua`, UPGRADES) | 6 upgrades, 183/s total | Done in 7 min, and just 17% of the 1,058/s ceiling. | Add more tiers with a 10x price growth so the garage lasts hours, not minutes. |
| HR Department costs (`Poaching.HRDepartment`) | 522,500 total | All 5 levels bought by hour 5. Defence becomes free for everyone. | Raise about 10x, or make it the main Cash sink. |
| Base slots (`BaseEmployeeSlots`) | 5 | Filled at minute 7, so slots are no goal after that. | Start at 3 and unlock more with Cash or IPO perks. |
| Luck Boost text (`ShopConfig`) | "2x rare employee chance" (now fixed) | The real effect is x1.2 on Legendary (finding 6). | Text changed to show the real odds. Still open: make the boost stronger (for example x3 weights). The design rule says to show real odds. |
| Auto-Hatch (`ShopConfig`) | Only saves clicks | No effect on income (finding 7). | Also hatch eggs while the player is away, so they join the team the moment the egg is ready. |
| Offline cap and rate (`TycoonCore.lua`) | 8 h at 50% | Idlers get 17% of a 24-h day (finding 9). | Fine for now. Tell players clearly on the screen, or let IPO's Night Shift perk extend it. |
| Rare/epic income gaps (`CreatureConfig.Creatures`) | Common 2 to 3, Legendary 150 to 175 | A Legendary is 50x a Common. Poaching one is a huge swing, but Legendaries can't be poached, so only Epic and below are targets. | Fine; just keep an eye on how it feels once poaching is live. |
| IPO thresholds (`IpoConfig.lua`) | Retuned (Seed 1,800, growth x2.5) | Was Placeholder, Seed in 9 min (finding 10). | Done on `ipo-retune`: see section 3. |
| Day-1 Cash packs (`ShopConfig` minCash) | 250 / 2,500 / 15,000 | At minute 0 the Vault (299 R$) gives 15,000: all upgrades and a Startup egg at once. Later the packs scale with income and become useless, because Cash has no use (finding 3). | Fine for monetisation; recheck after the economy changes above. |

## 6. Unfair or boring: summary

- **Boring:** the wall after the first 5 hours (findings 2 and 3), and the first stage of the IPO being instant.
- **Possibly unfair:** Luck Boost (misleading text), Auto-Hatch (does nothing for income). Neither is a pay-to-win problem, since the others are all fair and nothing is locked behind a pass.
- **Fair:** 2x Cash and VIP (pure speed), and the 10x gap between active and idler players matches the 60x gap in playtime.

## 7. Daily login calendar (milestone 6)

`DailyConfig.lua`: Day 1 = 5 min of income, Day 2 = 10 min, Day 3 = Garage Egg, Day 4 = 20 min, Day 5 = Startup Egg, Day 6 = 30 min, Day 7 = Unicorn Egg + 3 Shares. A Cash day gives at least $300 (`MinCash`). Missing one day keeps your place; two or more go back to Day 1 (`GraceDays = 1`).

Rerun with `python3 tools/economy_sim.py --daily --runs 30`. Every simulated player claims at the first login of every day (the worst case). IPO on, no passes, no perks, 30 days, median of 30 runs.

| Behaviour | Calendar | 1st IPO, minutes online (wall clock) | IPOs by day 7 | IPOs by day 30 | Shares at day 30 |
|---|---|---|---|---|---|
| active | none | 11.7 (hour 0) | 10 | 12 | 179 |
| active | **DailyConfig** | **11.7 (hour 0)** | **10** | **12** | **192 (+8%)** |
| active | DailyConfig, but Cash counts as valuation | 11.3 (hour 0) | 10 | 12 | 190 (+6%) |
| active | too generous (Startup d3/d5, Unicorn d7 + 10 Shares) | 11.7 (hour 0) | 10 | 12 | 220 (+23%) |
| casual | none | 10.0 (hour 24) | 7 | 10 | 229 |
| casual | **DailyConfig** | **10.0 (hour 24)** | **7** | **10** | **246 (+7%)** |
| casual | DailyConfig, but Cash counts as valuation | 10.0 (hour 24) | 7 | 10 | 254 (+11%) |
| casual | too generous | 10.0 (hour 24) | 7 | 10 | 274 (+20%) |
| idler | none | 2.0 (hour 48) | 6 | 10 | 210 |
| idler | **DailyConfig** | **1.0 (hour 24)** | **6** | **10** | **174 (-17%)** |
| idler | DailyConfig, but Cash counts as valuation | 1.0 (hour 24) | 6 | 10 | 180 (-14%) |
| idler | too generous | 1.0 (hour 24) | 6 | 10 | 206 (-2%) |

- **The first IPO and the IPO counts don't move** for active and casual players. The only lever is Shares: about +7% over 30 days.
- **Calendar Cash is a gift and stays out of the valuation** (`DailyServer` adds it to Cash only; the simulator asserts it). Correction to `docs/M6_PLAN.md` section 2: the plan says counting it would bring the first IPO 25% sooner (8.7 min). The real hook doesn't reproduce that: before the first IPO the only calendar Cash is Day 1 (about $300, 0.4% of the IPO-ready valuation), so the first IPO moves from 11.7 to 11.3 min (-3%). The rule is still right: later Cash days (20-30 min of income) would add real valuation to every run.
- **The idler's first IPO moves from hour 48 to hour 24**, and their Shares fall. Both come from the simulator going public the moment it can (an earlier IPO pays the base 10 Shares instead of a bigger offline overshoot; see section 3b). It is not a real loss for players.



## 10. Overhaul 2: the new economy (2026-10-19, the owner's numbers and written OK)

Everything in this section is read by `python3 tools/economy_sim.py --o2` straight from `OfficeConfig.lua`, `CreatureConfig.lua` and `IpoConfig.lua` (through Luau: `LUAU=/path/to/luau`), so nothing here is a hand copy. Sections 1 to 9 above describe the game before overhaul 2 and are kept as history (their CONFIG block still holds the old numbers).

### 10.1 The ladder

| Stage | Valuation to reach it | What it unlocks in SHOP > Office |
|---|---|---|
| Garage | 0 | the Garage's 12 items, desks 2 and 3 |
| Seed | $30K | the Small Office ($12K), 11 items, desk 4 |
| Series A | $10M | the Big Office ($3M), 11 items, desk 5 |
| Series B | $100M | the Small Corporate ($25M), 11 items |
| Series C (new) | $300M | the Big Corporate ($70M), 11 items |
| IPO-ready | $1B | the HQ Tower ($250M), 8 items, and going public |

- Valuation is still the Cash earned in the run, but **offline Cash and Cash packs count 10%** (`OfficeConfig.GiftValuationShare`): their Cash is paid in full, they just can't skip a stage. The owner's D-C decision (offline pay stays 50% of Income for up to 8 h) is kept.
- `StageGrowthPerIpo` 2.5 → **1.1**: later runs are faster through the IPO multiplier and what is kept (employees, desks, perks).
- Shares: `SharesPerIpo` 10 → **40**, `SharesGrowthPerIpo` 0.8 → **0.5** (a run is ~20 h now, was 12 min): IPO 1 = 40, IPO 2 = 60, IPO 3 = 80 (x2 with Shareholder). The perk shop (1,770 Shares) is unchanged.
- Income = (items' income x the building's **office** multiplier + employees' income x its **team** multiplier) x the IPO multiplier x passes.

| Building | Price | Office x | Team x |
|---|---|---|---|
| Garage | free | 1 | 0.1 |
| Small Office | $12K | 2 | 0.8 |
| Big Office | $3M | 3 | 5.1 |
| Small Corporate | $25M | 3.3 | 9.2 |
| Big Corporate | $70M | 3.8 | 15.8 |
| HQ Tower | $250M | 4.4 | 20 |

### 10.2 Workstations, eggs, hires, HR

- **Desks:** 1 free, then $2.5K and $5K (Garage), $60K (Seed), $1.5M (Series A): 5 in all, as the old 5 base slots. **Extra Employee Slots stays exactly +3 free** workstations, the Extra Desk perk +1 per level: 11 at most (the hire spots). Desks are kept through an IPO (the `office` save section).
- **Eggs:** Garage $800 (was 250), Startup $40K (was 2,500), Unicorn $2M (was 25,000). Hatch times, odds and creature incomes are unchanged; an employee earns its income x the building's team multiplier.
- **Direct hires (Office > Hire):** commons $4.6K, uncommons $13K: 4x what a Garage Egg pays on average for that rarity ($1.14K, $3.2K). Fixed creature, no roll (FR-13 untouched). Shown with the egg comparison.
- **HR Department:** $5K, $150K, $3M, $40M, $200M (was 2.5K to 350K). **Poach cost** = 300 s of the employee's income x the attacker's team multiplier (at least $500).

### 10.3 The office catalog (64 items)

Income is per second before the building's office multiplier. Effects: calls / sprint / bug / brainstorm / pitch = that founder activity pays that share more (the activities come in phase 3), hatch = eggs hatch that share faster, unlock bug = production bugs start.

| # | Item | Stage | Price | Income (base, /s) | Effect |
|---|---|---|---|---|---|
| 1 | 🪑 Desk | Garage | free | 1 |  |
| 2 | ☕ Coffee Machine | Garage | $120 | 1 |  |
| 3 | 🖥️ Second Monitor | Garage | $250 | - | sprint 0.25 |
| 4 | 💻 Laptop | Garage | $450 | 1 |  |
| 5 | 📡 Router | Garage | $700 | - | calls 0.2 |
| 6 | 💺 Better Chair | Garage | $1K | - | sprint 0.2 |
| 7 | 🧃 Mini Fridge | Garage | $1.4K | - | brainstorm 0.3 |
| 8 | 🗄️ Server Rack | Garage | $2K | 1 | unlock "bug" |
| 9 | 🎧 Headset | Garage | $2.4K | 1 | calls 0.15 |
| 10 | 📋 Whiteboard | Garage | $2.8K | - | brainstorm 0.5 |
| 11 | 📚 Bookshelf | Garage | $3.8K | - | pitch 0.2 |
| 12 | 💡 Neon Logo | Garage | $4K | 1 |  |
| 13 | 🧍 Standing Desks | Seed | $15K | 23 |  |
| 14 | 🍽️ Team Table | Seed | $30K | 32 |  |
| 15 | 📞 Phone Booth | Seed | $50K | - | calls 0.25 |
| 16 | 🗣️ Meeting Corner | Seed | $80K | 45 |  |
| 17 | 🌿 Plant Wall | Seed | $120K | 59 |  |
| 18 | ☕ Espresso Bar | Seed | $200K | 77 |  |
| 19 | 📽️ Pitch Screen | Seed | $350K | - | pitch 0.25 |
| 20 | 🖨️ Printer Station | Seed | $550K | 113 |  |
| 21 | 📶 Wi-Fi Mesh | Seed | $900K | 147 |  |
| 22 | 🧰 Dev Kit Shelf | Seed | $1.5M | - | sprint 0.3 |
| 23 | 🎨 Brand Mural | Seed | $2.5M | 226 |  |
| 24 | 🚪 Meeting Room | Series A | $2.5M | 46 |  |
| 25 | 🧪 QA Lab | Series A | $3.5M | - | bug 0.5 |
| 26 | ✏️ Design Studio | Series A | $4.5M | 64 |  |
| 27 | 🖧 Server Row | Series A | $6M | 77 |  |
| 28 | 🍿 Snack Bar | Series A | $7.5M | 86 |  |
| 29 | 🎙️ Podcast Booth | Series A | $9M | - | calls 0.3 |
| 30 | 🧠 Whiteboard Wall | Series A | $11M | - | brainstorm 0.5 |
| 31 | 🎮 Game Corner | Series A | $14M | 118 |  |
| 32 | 📈 Analytics Screens | Series A | $17M | 136 |  |
| 33 | 😴 Nap Pod | Series A | $21M | - | hatch 0.15 |
| 34 | 🪧 Rooftop Sign | Series A | $25M | 181 |  |
| 35 | 🏭 Data Center Room | Series B | $12M | 67 |  |
| 36 | 📣 Marketing Floor | Series B | $15M | 80 |  |
| 37 | 🤝 Recruiting Office | Series B | $19M | - | hatch 0.2 |
| 38 | 🛋️ Lounge Sofas | Series B | $23M | 100 |  |
| 39 | 🎓 Training Room | Series B | $28M | 114 |  |
| 40 | 🎧 Customer Success Desk | Series B | $33M | - | calls 0.35 |
| 41 | 🛡️ Security Desk | Series B | $38M | 133 |  |
| 42 | 📬 Mail Room | Series B | $44M | 147 |  |
| 43 | 📖 Library | Series B | $50M | 160 |  |
| 44 | 🎬 Video Studio | Series B | $55M | - | pitch 0.3 |
| 45 | 🫘 Coffee Roastery | Series B | $60M | 187 |  |
| 46 | 🥗 Cafeteria | Series C | $30M | 94 |  |
| 47 | 🏋️ Gym | Series C | $40M | 113 |  |
| 48 | 🌇 Rooftop Terrace | Series C | $50M | 132 |  |
| 49 | ⚖️ Legal Office | Series C | $62M | - | bug 0.5 |
| 50 | 🎤 Demo Stage | Series C | $75M | 160 |  |
| 51 | 🔬 Innovation Lab | Series C | $90M | - | sprint 0.4 |
| 52 | 🧘 Wellness Room | Series C | $105M | 190 |  |
| 53 | 🥂 Investor Lounge | Series C | $120M | - | pitch 0.4 |
| 54 | 🏟️ Auditorium | Series C | $140M | 228 |  |
| 55 | 🌳 Green Roof | Series C | $165M | 247 |  |
| 56 | 🖼️ Art Gallery | Series C | $190M | 275 |  |
| 57 | 🪑 Boardroom | IPO-ready | $150M | 207 |  |
| 58 | 💹 Trading Screens | IPO-ready | $200M | 248 |  |
| 59 | 📰 Press Room | IPO-ready | $260M | - | pitch 0.5 |
| 60 | 🏢 Executive Floor | IPO-ready | $330M | 310 |  |
| 61 | 🏆 Trophy Wall | IPO-ready | $420M | 351 |  |
| 62 | 🚁 Helipad | IPO-ready | $520M | 413 |  |
| 63 | 🏛️ Shareholder Hall | IPO-ready | $630M | 455 |  |
| 64 | 🔔 Golden Bell | IPO-ready | $750M | 517 |  |

### 10.4 Paid items: what changes for players (Robux prices and product IDs never change)

| Item | Before | Overhaul 2 | Fair? |
|---|---|---|---|
| 2x Cash (199) | x2 Cash | x2 Cash (and x2 valuation from income) | yes: Seed in 27 min instead of 55 for a perfect player |
| VIP (249) | x1.5 Cash | unchanged | yes |
| Extra Employee Slots (149) | +3 slots | **+3 free workstations**, on top of the 5 a player can buy | yes: never less than +3 |
| Shareholder (199) | x2 Shares | x2 Shares (IPOs pay 4x more Shares now) | yes |
| Auto-Hatch, Headhunter | | unchanged | yes |
| Pile / Bag / Vault of Cash (29/99/299) | 10 / 45 / 180 min of income, min $250 / $2.5K / $15K, all counted as valuation | same Cash (income-scaled), **10% counted as valuation** | yes: same buying power; it can no longer skip a funding stage |
| Luck Boost, Instant Hatch, Poach Shield | | unchanged | yes |

### 10.5 Daily rewards and goals

- Daily Cash days are minutes of income (5/10/20/30) with a $300 floor: they scale by themselves; eggs (days 3, 5, 7) are worth more now with the new egg prices; Day 7's 3 Shares stay. No number changed in `DailyConfig`.
- The goal chain follows the ladder: Answer 3 calls, Own 3 office items, Hire 3, Calls in a row, the Server Rack, Seed, **Move into the Small Office**, Hire 5, Series A, **the Big Office**, Series B, **the Small Corporate**, **Series C**, **the Big Corporate**, IPO-ready, the first IPO.

### 10.6 The sim: the first run, minutes of active play (median of 12 runs; perfect player)

| Stage | Valuation | Reached at (median) | Range | Target |
|---|---|---|---|---|
| Seed | 30.00K | 55 min | 51 min to 57 min | 60 min to 75 min |
| Series A | 10.00M | 2.9 h | 2.8 h to 3.0 h | 2.5 h to 3.5 h |
| Series B | 100.00M | 6.8 h | 6.2 h to 7.0 h | 6.0 h to 8.0 h |
| Series C | 300.00M | 10.8 h | 9.3 h to 11.4 h | 11.0 h to 13.0 h |
| IPO-ready | 1.00B | 17.7 h | 14.8 h to 19.0 h | 18.0 h to 22.0 h |

Longest wait between two purchases or hatches in the first hour (the activities fill it): median 8 min

### The first hour's purchases (items, desks, buildings, eggs; until Seed when it comes first)

| Player | Seed (median) | Seed range | Longest wait between two purchases (worst run) | Median run | Mean wait |
|---|---|---|---|---|---|
| perfect (best payback first, waits for it) | 55 min | 51 min to 57 min | 8 min | 8 min | 3 min |
| guided (follows the blackboard: cheapest first) | 65 min | 56 min to 68 min | 7 min | 7 min | 4 min |

The guided player's purchases (seed 1): 2s Desk, 88s Coffee Machine, 3 min Second Monitor, 4 min Laptop, 7 min Router, 10 min Better Chair, 14 min Mini Fridge, 20 min Server Rack, 25 min Headset, 30 min Desk 2, 31 min Garage Egg, 36 min Whiteboard, 42 min Bookshelf, 48 min Neon Logo, 55 min Desk 3, 56 min Garage Egg, 57 min Garage Egg, 58 min Garage Egg
Longest stretch with nothing to do in the first hour (purchases, hatches, calls, sprints, brainstorms, bugs; overhaul 2 phase 3's real clocks: a call every 20 to 40 s from the Desk, a sprint every 3.5 min, a brainstorm every 5 min from the first hire, a bug every 4 to 7 min from the Server Rack): worst 40s, median 40s, under the brief's 2 minutes (`o2_dead_time`).
Items bought by the IPO bell: median 64 of 64; Income at the bell: 34.50K/s

One run's purchases (seed 1): 2s Desk, 88s Coffee Machine, 3 min Laptop, 10 min Server Rack, 10 min Second Monitor, 16 min Headset, 18 min Router, 25 min Neon Logo, 27 min Better Chair, 30 min Desk 2, 32 min Garage Egg, 34 min Mini Fridge, 38 min Whiteboard, 44 min Desk 3, 45 min Garage Egg, 46 min Garage Egg, 48 min Garage Egg, 52 min Bookshelf, 67 min Small Office, 72 min Standing Desks, 76 min Team Table, 82 min Meeting Corner, 87 min Plant Wall, 1.6 h Espresso Bar, 1.6 h Phone Booth, 1.7 h Printer Station, 2.0 h Wi-Fi Mesh, 2.4 h Brand Mural, 2.4 h Startup Egg, 2.4 h Startup Egg, 2.4 h Startup Egg, 2.4 h Desk 4, 2.4 h Startup Egg, 2.4 h Startup Egg, 2.4 h Startup Egg, 2.5 h Startup Egg, 2.5 h Startup Egg, 2.5 h Startup Egg, 2.6 h Dev Kit Shelf, 2.6 h Pitch Screen ...

### Later runs (employees and desks kept, IPO multiplier, thresholds x1.10 per IPO)

| Run | Reaches IPO-ready at |
|---|---|
| 1 | 17.9 h |
| 2 | 10.5 h |
| 3 | 9.1 h |
| 4 | 8.5 h |

### With the 2x Cash pass (first run)

| Seed | Series A | Series B | Series C | IPO-ready |
|---|---|---|---|---|
| 27 min | 87 min | 3.3 h | 5.5 h | 9.1 h |

### Direct hires (OfficeConfig.hireList)

| Creature | Rarity | Price | An egg pays on average |
|---|---|---|---|
| CoffeeCapybara | Common | 4.60K | 1.14K (Garage Egg) |
| CodingCat | Common | 4.60K | 1.14K (Garage Egg) |
| PixelPigeon | Common | 4.60K | 1.14K (Garage Egg) |
| HustleHamster | Uncommon | 13.00K | 3.20K (Garage Egg) |
| BugBeetle | Uncommon | 13.00K | 3.20K (Garage Egg) |
| MemoMole | Uncommon | 13.00K | 3.20K (Garage Egg) |


What this does not tell you: the perfect player buys the best payback the moment it can and never pauses, so real players are slower (a guess: +10 to 25%); the guided player (cheapest first, as the blackboard suggests, and a Garage Egg whenever a workstation is free) is the closer stand-in for a new player and reaches Seed at about 65 min. The founder activities are modeled at the proposal's rates (calls 0.25, coding sprint 0.15, brainstorm 0.07, production bug 0.08 seconds of Income per second, 85% attention): phase 3 built them (calls live on every server since then). The "longest wait in the first hour" is between purchases or hatches; the activities (a call every 20 to 40 s, a sprint every 3 min) fill it. Offline Cash is not modeled (active play only).

### 10.7 Existing saves (the migration)

The first load under overhaul 2 gives a save **the building its old stage showed** (old thresholds 1,800 / 6,300 / 23,400 / 81,000 x2.5 per IPO, frozen in `OfficeConfig.LegacyStages`), written to `pokedex.active.building` with the mark `active.o2 = 1`, and **4 bought desks** (its old 5 base slots) in the new `office` section. Cash, Shares, employees, perks, owned upgrades, the IPO count and the valuation are untouched. Checked on the owner's own test save in Studio: IPO count 1, valuation $1.9M (old IPO-ready) → keeps the Big Corporate; under the new ladder that valuation is Seed, so Seed's items are what unlocks next.

### 10.8 First-hour pacing (2026-10-19, after overhaul 2)

The report of overhaul 2 found a 14-minute stretch with no purchase in the first hour, between the Server Rack (about minute 10) and the Neon Logo (about minute 24): the perfect player saved for the Neon Logo ($5.5K, the best payback) and bought nothing else. The owner asked for a purchase about every 5 minutes, with Seed kept at about 60 to 75 minutes.

| Item | Before | After |
|---|---|---|
| 🎧 Headset (new, Garage, between the Server Rack and the Whiteboard) | - | $2.4K, income 1, calls pay 15% more |
| 💡 Neon Logo | $5.5K, income 2 | $4K, income 1 |
| 📡 Router | $700, calls 0.2 | unchanged |

| The sim, 12 runs each (`--o2`, the same code on `main` and here) | Before | After |
|---|---|---|
| Longest wait between two purchases in the first hour, perfect player (worst run) | 15 min | 8 min |
| The same, guided player (follows the blackboard) | 12 min | 7 min |
| mean wait (perfect / guided) | 3 / 4 min | 3 / 4 min |
| Seed (perfect / guided, median) | 57 / 72 min | 55 / 65 min |
| IPO-ready, first run (perfect, median) | 18.1 h | 17.7 h |

Why these: the catalog's prices must grow inside a stage (`tools/office_test.py`), so the Router can only move between the Laptop ($450) and the Better Chair ($1K) and the Neon Logo, the Garage's last item, can't go under the Bookshelf ($3.8K). A search over every Router and Neon Logo price and income in those bounds (with and without one new item, both players, 9 runs each) found no change of those two alone under 8 min that kept Seed above 50 min for the perfect player; the Headset in the gap and a cheaper, smaller Neon Logo give 7 to 8 min with Seed where it was. The waits that are left (about 7 min) are the Garage's dearest buys, Desk 3 ($5K) and the Bookshelf, at the end of the hour; the activities fill them (worst stretch with nothing to do: 40 s). The whole run is about 2% faster (the Headset's calls bonus lasts all run): IPO-ready 17.7 h against 18.1 h on `main` (same 12 runs), still inside the runs' range (14.8 h to 19 h). An existing save keeps every item it owns; the Neon Logo's price only matters to someone who hasn't bought it.

