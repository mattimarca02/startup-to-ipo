# Long game: the IPO is the last thing (proposal, design only)

Branch `active-loops`; no game code, no `IpoConfig` or perk number changed. Owner's direction: first IPO after **50+ engaged hours**, every later loop 50+ h, tasks are the core. **Supersedes** the pacing and Shares parts of `docs/ACTIVE_LOOPS_PROPOSAL.md` and `docs/ECONOMY.md` 3-3e. Numbers: `python tools/economy_sim.py --long --runs 40` (item list = data `LONG_ITEMS`). **Engaged** = a task answered and graded by the server in the last 3 minutes; "hour" below = engaged hour. Kept: calls pay 7 s of Income, task Cash counts toward valuation, the Cash pass multiplies it, pitch Shares never doubled, Investor Day prizes cosmetic.

**Principle: Cash can only fill a rung, never skip it.** Money buys sooner inside a rung; only engaged play moves the clock.

## 1. Pacing: a target to verify, not a result

The ladder (section 3) is **fitted** so an always-engaged typical player takes 1.5 / 4 / 6.5 / 9 / 24 / 15 h per rung (**60 h**; **57 h** for the regular player with away pay). So "50+ hours" is the input of the fit; only Studio can measure the real task bonus and item Incomes. Sensitivity (regular player, IPO 1):

| Change (one at a time) | Hours | | Changes stacked | Hours |
|---|---|---|---|---|
| none (draft) | **57** | | optimistic: Income x1.25, prices -30% | 32 |
| task bonus x0.5 / none | 74 / 107 | | pessimistic: bonus x0.5, Income x0.8, prices +30% | 120 |
| item Income x0.8 / x1.25 | 71 / 46 | | worst: no bonus, Income x0.8, prices +30% | 173 |
| prices (thresholds follow) -30% / +30% | 40 / 74 | | | |

**Range: 40-107 h for one wrong assumption, 32-173 h stacked.** Prices are refitted after the measurement (section 8); 50+ h is claimed only then.

Weeks to IPO 1 / 10: dedicated (2 h/day) **4** / 52; regular (1 h/day) **9** / 110; casual (3 x 1 h/week) **22** / 270.

Prices and thresholds grow **+10% per loop** (`StageScale`): loops 57 / 54 / 57 h, IPO 10 at 686 h in total (+5%: 57 / 52 / 52; +15%: 57 / 56 / 62; flat: 57 / 49 / 47).

## 2. Clock rules: engaged, away, daily cap

- **Engaged** is decided by the server only: a graded task answer (not skipped, not auto-resolved, reaction at least 0.25 s, not flagged) in the last 180 s. Movement, jumping, chat or client reports never count (ACTIVE doc section 2).
- **Valuation:** engaged Cash counts **100% for the first 4 engaged hours per UTC day, 10% after**.
- **Away** (not engaged, online or offline): the startup banks **10% of the base Income** (no passes, boosts or chain) for up to **2 h** per return (Night Shift: +30 min per level, 4 h at most). The next graded answer pays the bank at once; **10%** of it counts toward valuation. Tasks, auto-resolve and chains pay nothing away; Cash packs and daily Cash never count.

| Player, 24/7 online (sim, median) | Before: any input = engaged, no cap | After: graded task, 4 h/day then 10% |
|---|---|---|
| **macro** (input only, no tasks) | 115 h, **4.8 days** | **never** (pays nothing, counts nothing) |
| **task-bot** at the budget cap | 55 h, **2.3 days** | 172 h online, **7.2 days** |
| pulse-bot (3 min of tasks every 2 h) | 63 days | 63 days (equals a regular player) |
| for scale: dedicated 2 h/day / regular | 30 / 63 days | 30 / 63 days |

The macro hole is closed. A perfect 24/7 task-bot is 3x slower than before but still **4x faster per day than a dedicated human** (7.2 vs 30 days); 3 h/day then 5% gives 11 days, 2 h then 5% 14 (question 2). A check-in player (1 min/day) opens Series C+D in about 1.7 years and never reaches the IPO (today's rule: 21 h, 5 weeks).

**New top-level save section `away`** (rule A10) = `{ engagedDay = UTC day number, engagedSeconds, bankSeconds }`, optional, clamped on load, stale day ignored, entry in `KNOWN_SECTIONS`. **This replaces the old claim "no new section": PR 2 needs Shut down all servers.** Rollback floor stays `V_launch` (PUBLISH_RULES section 2): code from M4 on keeps `away` frozen, so a rollback loses nothing but runs today's offline rule (50%, 8 h, 100% valuation) until forward again; never restore below `V_launch`. No real saves exist yet.

## 3. The ladder is data: 6 rungs, 85 items

**Rule:** valuation to enter the next rung = **1.5 x the price of everything in the rungs so far** (`LONG_K`), so hours per rung are an *output* of the prices. Item price = `s x sqrt(Income before x Income gained)` (quick early waits), one fitted `s` per rung; desk = half its hire, office = 0.7 x. A hire's price is what its egg(s) cost; egg price = the rung's first hire.

| Rung | Hours (cum.) | Income ceiling /s | Enter next at | Egg tier (price) | Desk cap /s | Task budget |
|---|---|---|---|---|---|---|
| Garage | 1.5 (1.5) | 194 | $197K | Garage (2.3K; today 250) | 25 | 0.85 |
| Seed | 4.0 (5.5) | 414 | $6.4M | Startup (310K; today 2.5K) | 60 | 0.85 |
| Series A | 6.5 (12) | 1,099 | $37M | **Scale-up** (1.4M) | 180 | 0.95 |
| Series B | 9.0 (21) | 2,394 | $152M | Unicorn (7.1M; today 25K) | 300 | 1.05 |
| Series C+D | 23.9 (45) | 5,834 | $927M | **Decacorn** (26M) | 540 | 1.15 |
| Pre-IPO | 15.0 (60) | 8,614 | $1.85B | **Blue-Chip** (70M) | 650 | 1.25 |

**The item list (draft for the owner to approve; price / +Income; Income/s; in buying order)**

| Rung | Offices | Upgrades | Desks (price) | Hires |
|---|---|---|---|---|
| Garage | Garage 0 | Desk 0/+1; Coffee Machine 1.1K/+2; Laptop 4.2K/+5; Server Rack 13K/+15; Whiteboard 28K/+40; Neon Logo 72K/+120 | 1: 0, 2: 3.6K | Coding Cat 2.3K/+3; Bug Beetle 7.2K/+8 |
| Seed | Co-working Loft 570K | Standing Desks 160K/+6; Espresso Bar 230K/+12; Dev Laptops 320K/+20; Rack Room 410K/+30; Glass Boardroom 490K/+38; Rooftop Sign 560K/+44 | 3: 150K, 4: 320K | Sales Shark 310K/+20; Server Sloth 640K/+50 |
| Series A | Downtown Floor 2M | Open Plan 560K/+12; Quiet Pods 810K/+24; Design Studio 1.1M/+40; Data Closet 1.5M/+60; Demo Theater 1.7M/+76; Lobby Screen 2M/+88 | 5: 690K, 6: 1.4M, 7: 1.6M | Ledger Llama 1.4M/+60; Unicorn CEO 2.7M/+150; Venture Dragon 3.2M/+175 |
| Series B | Campus Wing 7.8M | Game Room 2.3M/+25; Gym 3.2M/+50; Cafeteria 4.2M/+80; Data Center 5.3M/+120; Auditorium 6.2M/+150; Fountain 7.5M/+175 | 8: 3.5M, 9: 4.4M, 10: 5.4M | Venture Dragon 7.1M/+175; Growth Gecko 8.8M/+220; Compliance Cobra 11M/+300 |
| Series C+D | Tech Campus 23M; Glass Tower 31M | Robot Barista 6.8M/+25; Sky Lounge 9.6M/+50; Mega Rack 12M/+80; Innovation Lab 15M/+120; Atrium 17M/+150; Helipad 19M/+175; Trading Floor 9.2M/+30; Spa 13M/+60; Quantum Rack 17M/+95; Observatory 20M/+140; Ballroom 23M/+175; Statue 25M/+200 | 11: 13M, 12: 15M, 13: 20M, 14: 21M, 15: 23M | Compliance Cobra 26M/+300; Platform Panda 31M/+380; Closer Condor 39M/+460 (x2: 41M); Brand Badger 47M/+540 |
| Pre-IPO | Global HQ 62M | Marble Lobby 18M/+40; War Room 25M/+80; Server Farm 32M/+130; Roadshow Jet 39M/+190; Bell Tower 47M/+260; Golden Bell 51M/+300 | 16: 35M, 17: 39M, 18: 41M | Brand Badger 70M/+540; Board Bison 78M/+620 (x2: 81M) |

**Hire types: 18** = today's 12 (Income 2 to 175) **+ 6 new**: Growth Gecko 220 (marketing), Compliance Cobra 300 (finance), Platform Panda 380 (engineering), Closer Condor 460 (sales), Brand Badger 540 (marketing), Board Bison 620 (finance). **Desks: 18** (today 5 base slots, +3 with the Extra Slots pass; pass desks not simulated, at most +15% Income at the top: measure in PR 3). **Desk cap:** a desk employs a creature only up to its office's Income (a Venture Dragon in a garage desk earns 25/s), so kept, fed or poached hires cannot skip rungs (section 7). After an IPO kept employees refill the same desks **free**. A hire row is the *planned* creature of an egg; the real roll stays random. **D9: the three new egg tiers go into `CreatureConfig.Eggs`, so restricted players roll through `CreatureConfig.fixedHire`; the fixed-order tests must cover them.** **Desks, caps and kept hires change `EmployeeServer`/`CreatureConfig`: their own PR (PR 3).**

## 4. Content, with the owner's scope cuts

Cuts (owner approved): all 20 tasks kept (paired demo and Investor Day **outside** the 50 h path), Series C+D merged, decor 50 to 20, products 14 to 6, hire types 25 to 18. A task's tiers 2 and 3 appear one and two rungs later (a moment each).

| Rung | Offices / upgrades / desks / hires | Tasks (+tiers) | Eggs / products / decor / titles | Moments | Min per moment |
|---|---|---|---|---|---|
| Garage | 0 / 6 / 1 / 2 | 1 (+0) | 0 / 0 / 3 / 1 | 14 | 6 |
| Seed | 1 / 6 / 2 / 2 | 3 (+1) | 0 / 2 / 4 / 1 | 22 | 11 |
| Series A | 1 / 6 / 3 / 3 | 4 (+4) | 1 / 1 / 4 / 1 | 28 | 14 |
| Series B | 1 / 6 / 3 / 3 | 4 (+7) | 0 / 1 / 3 / 1 | 29 | 19 |
| Series C+D | 2 / 12 / 5 / 5 | 5 (+8) | 1 / 1 / 4 / 1 | 44 | **33** |
| Pre-IPO | 1 / 6 / 3 / 3 | 1 (+8) | 1 / 1 / 2 / 3 | 29 | 31 |
| **Total** | 6 / 42 / 17 / 18 | 18 (+28) | 3 / 6 / 20 / 8 | **166** | 22 |

Series C+D gets a moment only every 33 min: thicken it first. **Content minimum for the first 5.5 h (Garage + Seed):** 19 things to buy (9 exist today, re-priced; 10 new: Seed office, 6 upgrades, 3 desks), 4 tasks, 2 products, 7 decor, 2 titles: 36 moments, one per 9 min. Loops 2+ replay the ladder (one industry skin per IPO).

## 5. Shares, shop, and exactly what changes

`Shares = 20 x (1 + 0.25 x IPOs done) x min(ratio, 1.5) ^ 0.5` (was 10, 0.8, cap 2; x2 with the pass): 20, 25, 30 ... 65 per IPO; total 20 / 45 / 150 / 425 after IPO 1 / 2 / 5 / 10 (pass 40 / 90 / 300 / 850). Shop **750** (was 1,770): core 316 + prestige wing 434 (cosmetic).

**`IpoConfig`:** `SharesPerIpo` 10 to 20; `SharesGrowthPerIpo` 0.8 to 0.25; `SharesRatioCap` 2 to 1.5; perk costs (levels and keys unchanged) FasterEggs 1,2,3,5,7,10,16; ExtraIncubator 4,8; ExtraSlot 4,8,18; BaseLuck 1,2,3,5,7,10,16,24; CheaperPoach 2,3,4,6,8,11,15,20,28,40; Night Shift 2,4,7,12 and `perLevel` 7,200 to **1,800 s** (base away cap 2 h in `TycoonCore`); `Stages` **5 to 7** (add `SeriesCD`, `PreIpo` before `IpoReady`; valuations from section 3); `StageGrowthPerIpo ^ L` replaced by `StageScale(L) = (1 + 0.5 x L^0.75) x 1.10^L` for thresholds **and** every price; the IpoClient "wait longer" hint (cap 1.5). **`DailyConfig`:** Day 7 loses `shares = 3` (its egg = best tier already unlocked); a decor piece joins in PR 4. **`OnboardingConfig`:** goal "Reach Seed" (now 1.5 h) becomes "Buy 3 upgrades". **Tests:** of the 73 D1 checks about 28 hard-code old numbers and are rewritten (1,770 total and per-perk totals, "525 before D1", old and new level costs, Shares 10 / 0.8 / cap 2 and the 10 / 18 / 26 / 68 results, stages 1800 ... 81000 x 2.5, both `IPO_PERK_COSTS` checks, two old-save checks naming 90 and 1,245); the other 45 (keys, effects, pass 2x, save and load) stay. **Docs:** `ECONOMY.md` 3-3e, `D1_SHOP_OPTIONS.md`, PUBLISH_RULES section 2 (perk-level bullet), CLAUDE.md save notes, ROADMAP. **Sim:** `IPO_*`, `IPO_PERK_COSTS`. No real saves exist (PUBLISH_RULES section 2): levels only need clamping to `#costs`; after launch only add levels.

## 6. Money and passes

- **Shareholder pass (199 R$, 2001728902):** exactly **2x Shares**. It gives the **Boardroom skin and a gold chat tag (`ChatTags`) at purchase**. Its only progress edge is speed perks 2 IPOs sooner (IPO 4 vs 6): computed now (the +25% Income for the 154 speed Shares is an estimate) as **about 15 h by IPO 6, still 15 h at IPO 10 (2%)**; the old "10-15 h" claim is gone.
- **2x Cash pass:** valuation counts **base Cash** (doubled Cash would give owners IPO 1 in 28.6 h). At base: **48.7 h vs 57.1 h** (question 1). **Cash packs** are gifts, never valuation.
- **Every `addEarnings` call and what it passes:** (1) TycoonCore income loop (`:733`, each second): **base Income** (without the 2x Cash and VIP multipliers, with the IPO multiplier), only while engaged; (2) TycoonCore offline block (`:692`): replaced by the away payout, 10% of base Income; (3) `ShopServer.lua:539` Cash packs: **call deleted**; (4) `IpoServer.addEarnings` (`:125`), the single choke point: new `kind` argument (`engaged`, `away`, `task`, `debug`) applies the 4 h/day weight and saves `away`; (5) `IpoServer.lua:404/411` Debug grants: Studio only, bypass the weight; (6) new `TaskServer`: Cash with passes, valuation at base; (7) `DailyServer` never calls it (its BUG warning stays). The `TycoonCore.addEarnings` wrapper (`:478`) forwards `kind`.
- New products (cosmetic, fixed contents): Night Guard (8 h Poach Shield, 99 R$, `id = 0`, owner runs the sync), decor bundles. Never sold: stage skips, valuation, engaged-hour boosts, random boxes (D9).

## 7. New exploit: alt accounts feeding top hires

Kept employees carry over every IPO, so an alt that hatches Unicorn-tier eggs and "loses" them to a main account through poaching is now worth real hours. Sim (regular player; a fed hire is free):

| Case | IPO 1 | Loop 2 |
|---|---|---|
| no feeding | 57.1 h | 53.9 h |
| fed without limit, **no desk cap** | **22.0 h** | 23.2 h |
| R1 desk cap only | 43.8 h | 45.5 h |
| R1 + 2 poach-ins per UTC day | 43.9 h | 45.5 h (never binds) |
| R1 + **at most 6 per run** / **3 per run** | 50.9 h / **54.0 h** | 49.8 h / 51.7 h |

**Rules:** R1 desk caps by office; **R2 at most 3 poach-ins per account per run** (new section `lineage = { run = ipo.count, poachIns, poached = { [employeeId] = os.time() } }`, stale run = 0) and poach-won employees **do not carry over an IPO** (only hires you hatched); R3 poaching (either side) needs account age of 14 days or more and 10 engaged hours (`player.AccountAge`; not simulated). Three poach-ins leave the main 5% faster; per-day limits do not work.

## 8. PR plan (order changed), gates

| PR | Content | Size | Gate / test |
|---|---|---|---|
| 1 | Task engine + customer calls **with measurement hooks** (ACTIVE doc sections 2, 5) | L | daily_test; Studio |
| **G1** | **Studio playtests: measure the real task bonus and budget fill** (5 players, 2 rungs) | | measured f vs sim 0.32 / 0.50; refit prices (`f_mult`) before PR 2 |
| 2 | **Economy core:** base-Cash valuation, `kind` weights, engaged and away bank (`away`), `IpoConfig`, Daily Day 7, packs as gifts, sim and test sync. **Shut down all servers** | XL (800 Lua + 500 test; may split) | new test groups; macro and bot in Studio |
| 3 | Desks, caps, kept-hire free refill, `lineage`, poach limits (`EmployeeServer`) | M | caps, 3 poach-ins, 2-client poach |
| 4 | Office framework, Seed, Daily decor piece | L | rung unlock, both phone sizes |
| 5-6 | Tasks 2-5 and rungs A, B; then C+D, Pre-IPO, roadshow, products | M each | grading, budget per rung, `id = 0` |
| 7 | Prestige wing, skins, industry skin 1, Investor Day | M | rule A10, pass skin |

## 9. Risks and questions

Risks: retention over 100+ sessions; content volume; unmeasured Incomes and task bonus; a perfect task-bot. Not simulated: fun, real poaching, egg timers.

1. **Cash pass:** base valuation, owners 48.7 h vs 57.1 h (recommended), or slower?
2. **Task-bot residual:** accept 4 h/100% then 10% (7 days), or 3 h then 5% (11 days)?
3. **Desk caps** (a Dragon in a garage desk earns 25/s) and 3 poach-ins per run: OK?
4. **Launch scope:** Garage-B first (21 h, then a rung every 2 weeks) or all rungs?
5. Loop growth +10% and a Day 7 decor piece instead of 3 Shares: OK?
