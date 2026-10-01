# Economy report: Build your Startup!

Made with `tools/economy_sim.py` (Python, standard library only). Run it yourself:

```
python tools/economy_sim.py --runs 40
```

All game numbers are copied by hand into the CONFIG block at the top of the script, each with a comment saying which `.lua` file it came from. **If you change a game number, change it there too.** The simulator never changes the game.

> **IPO numbers are a PLACEHOLDER.** The stages, thresholds and multiplier in section 4 are made up (about 10x per stage, +0.5x income per IPO). They must be replaced with the real `IpoConfig.lua` once `milestone-4-ipo` is merged. Everything in the IPO column is only as good as those guesses.

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

**Not modelled:** poaching, Instant Hatch, Cash packs, the IPO shop, daily rewards (M6), events (M7). The simulated player is a perfect, never-distracted optimiser, so real players will be slower. Results are the median of 40 random runs (days 1, 3 and 7 are days of the player's own clock, starting at their first login).

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

## 3. IPO rebirth (placeholder numbers, 30 days)

Stages: Seed 50K, Series A 500K, Series B 5M, IPO-ready 50M valuation. Each IPO: income x(1 + 0.5 x IPOs) and the next run's thresholds x3. Employees are kept; Cash, upgrades and incubating eggs reset.

| Behaviour | Seed | Series A | Series B | First IPO | IPOs in 30 days | Multiplier at day 30 |
|---|---|---|---|---|---|---|
| active | 9 min | 5 h | 11 h | 59 h | 4 | x3.0 |
| casual | 9 min | 24 h | 48 h | 8.5 d | 2 | x2.0 |
| idler | 24 h | 48 h | 3 d | 10 d | 2 | x2.0 |

To change: the `IPO_*` values in the CONFIG block of the script.

## 4. Ten findings

1. **The first employee arrives at minute 5, not minute 1.** The simulated player buys three upgrades first (they pay back faster than an egg), then the first Garage egg at about minute 3, and it hatches 60 s later. M5's "free egg and first employee within 60 seconds" is needed; today nothing in the first minutes points at eggs.
2. **The whole "build phase" lasts 7 minutes.** All six garage upgrades and a full team of 5 are done by then (active and casual alike). After that, the garage has nothing left to buy: only 183 Cash/s comes from upgrades in total.
3. **Day-1 players hit a wall at about hour 5.** An active player has bought every HR level (522,500 in total) by hour 5 and meets a first Legendary around hour 5; by day 7 the team income is 875/s, which is exactly the maximum for 5 slots (5 x 175). Cash/h flattens from day 3 (1.28M) to day 7 (1.61M). From then on Cash has nothing to buy. This is the biggest boredom risk in the base game, and IPO has to fix it (see finding 10).
4. **Prices are tiny compared with income, so Cash is not the limit; time is.** At about 700 Cash/s, a Unicorn egg (25,000) costs 36 seconds of income and a Startup egg (2,500) costs 4 seconds. What actually slows the player down is 3 incubators and the hatch timers (60 s, 5 min, 15 min). Active players first buy a Startup egg at minute 7 and a Unicorn egg at minute 18.
5. **2x Cash makes progress 2.0x faster and nothing else.** It doubles Cash/h and cuts "all upgrades" from 7 to 4 min. It is the clearest pass and fair: a free player still gets the same content. VIP adds 1.5x for 249 R$ against 2x for 199 R$, so on Cash alone VIP is the worse deal; it relies on the tag and the lounge to sell. The two stack to x3, so buying both is worth about 1.5x more than 2x alone.
6. **Luck Boost is weak and its text is misleading.** It says "2x rare employee chance", but because the odds are scaled back to 100%, a Unicorn egg's Legendary chance only goes from 8.0% to 9.7% (x1.2) and a Startup egg's from 1.0% to 1.6%. The effect on income is +35% for a Startup egg and +17% for a Unicorn egg for 15 minutes, and only +8% to +9% on day-7 Cash/h for casual players. Players who pay 49 R$ expecting double Legendaries will feel cheated.
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
| Luck Boost text (`ShopConfig`) | "2x rare employee chance" | The real effect is x1.2 on Legendary (finding 6). | Change the text to match, or make the boost stronger (for example x3 weights). The design rule says to show real odds. |
| Auto-Hatch (`ShopConfig`) | Only saves clicks | No effect on income (finding 7). | Also hatch eggs while the player is away, so they join the team the moment the egg is ready. |
| Offline cap and rate (`TycoonCore.lua`) | 8 h at 50% | Idlers get 17% of a 24-h day (finding 9). | Fine for now. Tell players clearly on the screen, or let IPO's Night Shift perk extend it. |
| Rare/epic income gaps (`CreatureConfig.Creatures`) | Common 2 to 3, Legendary 150 to 175 | A Legendary is 50x a Common. Poaching one is a huge swing, but Legendaries can't be poached, so only Epic and below are targets. | Fine; just keep an eye on how it feels once poaching is live. |
| IPO thresholds (`IpoConfig.lua`) | Placeholder | Seed in 9 min (finding 10). | Re-run this simulator with the real file, then choose stages so Seed takes about 1 h. |
| Day-1 Cash packs (`ShopConfig` minCash) | 250 / 2,500 / 15,000 | At minute 0 the Vault (299 R$) gives 15,000: all upgrades and a Startup egg at once. Later the packs scale with income and become useless, because Cash has no use (finding 3). | Fine for monetisation; recheck after the economy changes above. |

## 6. Unfair or boring: summary

- **Boring:** the wall after the first 5 hours (findings 2 and 3), and the first stage of the IPO being instant.
- **Possibly unfair:** Luck Boost (misleading text), Auto-Hatch (does nothing for income). Neither is a pay-to-win problem, since the others are all fair and nothing is locked behind a pass.
- **Fair:** 2x Cash and VIP (pure speed), and the 10x gap between active and idler players matches the 60x gap in playtime.
