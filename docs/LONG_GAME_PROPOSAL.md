# Long game: the IPO is the last thing (proposal, design only)

Design only (branch `active-loops`): no game code, no `IpoConfig` or perk number changed. Owner's direction: first IPO after **50+ engaged hours**, every later loop 50+ h, tasks are the core. **Supersedes** the pacing and Shares parts of `docs/ACTIVE_LOOPS_PROPOSAL.md` and `docs/ECONOMY.md` 3-3e. Numbers: `python tools/economy_sim.py --long --runs 40` (items = data `LONG_ITEMS`). **Engaged** = a task answered and graded by the server in the last 3 minutes; "hour" below = engaged hour. Kept: calls pay 7 s of Income, task Cash counts toward valuation, the Cash pass multiplies it, pitch Shares never doubled, Investor Day prizes cosmetic.

**Principle: Cash can only fill a rung, never skip it.** Only engaged play moves the clock.
## 1. Pacing: a target to verify, not a result
The ladder (section 3) is **fitted** so an always-engaged typical player takes 1.5 / 4 / 6.5 / 9 / 24 / 15 h per rung (**60 h**; **57 h** for the regular player with away pay). "50+ hours" is the input of the fit; only Studio can measure the real task bonus and Incomes. Sensitivity (regular, IPO 1):

| Change (one at a time) | Hours | | Changes stacked | Hours |
|---|---|---|---|---|
| none (draft) | **57** | | optimistic: Income x1.25, prices -30% | 32 |
| task bonus x0.5 / none | 74 / 106 | | pessimistic: bonus x0.5, Income x0.8, prices +30% | 120 |
| item Income x0.8 / x1.25 | 71 / 46 | | worst: no bonus, Income x0.8, prices +30% | 172 |
| prices (thresholds follow) -30% / +30% | 40 / 74 | | | |

**Range: 40-106 h for one wrong assumption, 32-172 h stacked.** Prices are refitted after the measurement (section 8). Weeks to IPO 1 / 10: dedicated (2 h/day) **4** / 41; regular (1 h/day) **9** / 88; casual (3 h/week) **22** / 214.

Prices and thresholds grow **+5% per loop** (`StageScale`, decided): loops 1-3 take **57 / 51.5 / 52 h**, IPO 10 comes at 549 h in total (+10%: 57 / 54 / 57; +15%: 57 / 56 / 62; flat: 57 / 49 / 47).

## 2. Clock rules: engaged, away, daily cap

- **Engaged** is decided by the server only: a graded task answer (not skipped, not auto-resolved, reaction at least 0.25 s, not flagged) in the last 180 s. Movement, chat or client reports never count (ACTIVE doc section 2).
- **Valuation:** engaged Cash counts **100% for the first 3 engaged hours per day, 5% after**. The day is the daily calendar's: it starts at 08:00 UTC, `away.engagedDay = DailyConfig.dayNumber(os.time())` (the sim uses `(t - 8 h) // 24 h`).
- **Away** (not engaged, online or offline): the startup banks **10% of the base Income** (no passes, boosts or chain) for up to **2 h** per return (Night Shift: +30 min per level, 4 h at most). The next graded answer pays the bank; **10%** of it counts toward valuation. Cash packs and daily Cash never count.

| Player, 24/7 online (sim, median) | Before: any input = engaged, no cap | After: graded task, 3 h/day then 5% |
|---|---|---|
| **macro** (input only, no tasks) | 115 h, **4.8 days** | **never** (pays nothing, counts nothing) |
| **task-bot** at the budget cap | 55 h, **2.3 days** | 250 h online, **10.4 days** |
| pulse-bot (3 min of tasks every 2 h) | 63 days | 63 days (equals a regular player) |

The macro hole is closed. A perfect 24/7 task-bot is 4.5x slower than before but still **3x faster per day than a dedicated human** (10.4 vs 30 days; regular: 63). A check-in player (1 min/day) never reaches the IPO (today: 5 weeks).

**New top-level save section `away`** (rule A10) = `{ engagedDay = DailyConfig.dayNumber(os.time()), engagedSeconds, bankSeconds }`, optional, clamped on load, stale day ignored, in `KNOWN_SECTIONS`. PR 2 needs Shut down all servers; rollback floor stays `V_launch` (PUBLISH_RULES section 2): older code keeps `away` frozen and runs today's offline rule until forward again.

## 3. The ladder is data: 6 rungs, 97 items

**Rule:** valuation to enter the next rung = **1.5 x the price of everything in the rungs so far** (`LONG_K`), so hours per rung are an *output* of the prices. Item price = `s x sqrt(Income before x Income gained)` (quick early waits), one fitted `s` per rung; desk = half its hire, office = 0.7 x. A hire's price is what its egg(s) cost; egg price = the rung's first hire. **Order:** each rung's first office comes after its first 2 upgrades (so no rung opens with nothing to buy); in Series C+D every upgrade is two levels, I and II, at half price and half Income.

| Rung | Hours (cum.) | Income ceiling /s | Enter next at | Egg tier (price) | Desk cap /s | Task budget |
|---|---|---|---|---|---|---|
| Garage | 1.5 (1.5) | 194 | $197K | Garage (2.3K; today 250) | 25 | 0.85 |
| Seed | 4.0 (5.5) | 414 | $6.5M | Startup (310K; today 2.5K) | 60 | 0.85 |
| Series A | 6.5 (12) | 1,099 | $37.5M | **Scale-up** (1.4M) | 180 | 0.95 |
| Series B | 9.0 (21) | 2,394 | $153M | Unicorn (7.1M; today 25K) | 300 | 1.05 |
| Series C+D | 23.8 (45) | 5,834 | $937M | **Decacorn** (26M) | 540 | 1.15 |
| Pre-IPO | 15.0 (60) | 8,614 | $1.86B | **Blue-Chip** (70M) | 650 | 1.25 |

**The item list (draft for the owner to approve; price / +Income; Income/s; in buying order)**

| Rung | Offices | Upgrades | Desks (price) | Hires |
|---|---|---|---|---|
| Garage | Garage 0 | Desk 0/+1; Coffee Machine 1.1K/+2; Laptop 4.2K/+5; Server Rack 13K/+15; Whiteboard 28K/+40; Neon Logo 72K/+120 | 1: 0, 2: 3.6K | Coding Cat 2.3K/+3; Bug Beetle 7.2K/+8 |
| Seed | Co-working Loft 580K | Standing Desks 160K/+6; Espresso Bar 230K/+12; Dev Laptops 320K/+20; Rack Room 410K/+30; Glass Boardroom 500K/+38; Rooftop Sign 570K/+44 | 3: 150K, 4: 320K | Sales Shark 310K/+20; Server Sloth 650K/+50 |
| Series A | Downtown Floor 2M | Open Plan 560K/+12; Quiet Pods 810K/+24; Design Studio 1.1M/+40; Data Closet 1.5M/+60; Demo Theater 1.7M/+76; Lobby Screen 2M/+88 | 5: 690K, 6: 1.4M, 7: 1.6M | Ledger Llama 1.4M/+60; Unicorn CEO 2.7M/+150; Venture Dragon 3.2M/+175 |
| Series B | Campus Wing 7.8M | Game Room 2.3M/+25; Gym 3.2M/+50; Cafeteria 4.2M/+80; Data Center 5.3M/+120; Auditorium 6.2M/+150; Fountain 7.5M/+175 | 8: 3.5M, 9: 4.4M, 10: 5.4M | Venture Dragon 7.1M/+175; Growth Gecko 8.8M/+220; Compliance Cobra 11M/+300 |
| Series C+D | Tech Campus 23M; Glass Tower 31M (after Platform Panda) | **12 upgrades x 2 levels (each level: half price, half Income):** Robot Barista 3.4M/+12.5; Sky Lounge 4.9M/+25; Mega Rack 6.1M/+40; Innovation Lab 7.6M/+60; Atrium 8.6M/+75; Helipad 9.6M/+87.5; Trading Floor 4.7M/+15; Spa 6.6M/+30; Quantum Rack 8.6M/+47.5; Observatory 10M/+70; Ballroom 12M/+87.5; Statue 13M/+100 | 11: 13M, 12: 15M, 13: 20M, 14: 21M, 15: 23M | Compliance Cobra 26M/+300; Platform Panda 31M/+380; Closer Condor 40M/+460 (x2: 42M); Brand Badger 48M/+540 |
| Pre-IPO | Global HQ 62M | Marble Lobby 18M/+40; War Room 25M/+80; Server Farm 32M/+130; Roadshow Jet 39M/+190; Bell Tower 47M/+260; Golden Bell 51M/+300 | 16: 35M, 17: 39M, 18: 41M | Brand Badger 70M/+540; Board Bison 78M/+620 (x2: 81M) |

**Hire types: 18** = today's 12 (Income 2 to 175; Venture Dragon comes from the Scale-up egg, the tier of the rung where it is first bought) **+ 6 new**: Growth Gecko 220, Compliance Cobra 300, Platform Panda 380, Closer Condor 460, Brand Badger 540, Board Bison 620. **Desks: 18** (today 5 base slots, +3 with the Extra Slots pass, not simulated: at most +15% Income). **Desk cap:** a desk employs a creature only up to its office's Income, so kept, fed or poached hires cannot skip rungs (section 7); after an IPO kept employees refill the same desks **free**. A hire row is the *planned* creature; the real roll stays random. **D9: the three new egg tiers go into `CreatureConfig.Eggs` (restricted players use `fixedHire`; the fixed-order tests must cover them).** Desks, caps and kept hires change `EmployeeServer`/`CreatureConfig`: PR 3.

## 4. Content, with the owner's scope cuts

Owner's cuts: 20 tasks (paired demo and Investor Day **outside** the 50 h path), Series C+D merged, decor 50 to 20, products 14 to 6, hire types 25 to 18. Task tiers 2 and 3 appear one and two rungs later (a moment each).

| Rung | Offices / upgrades (levels) / desks / hires | Tasks (+tiers) | Eggs / products / decor / titles | Milestones | Moments | Min per moment |
|---|---|---|---|---|---|---|
| Garage | 0 / 6 / 1 / 2 | 1 (+0) | 0 / 0 / 3 / 1 | 0 | 14 | 6 |
| Seed | 1 / 6 / 2 / 2 | 3 (+1) | 0 / 2 / 4 / 1 | 0 | 22 | 11 |
| Series A | 1 / 6 / 3 / 3 | 4 (+4) | 1 / 1 / 4 / 1 | 0 | 28 | 14 |
| Series B | 1 / 6 / 3 / 3 | 4 (+7) | 0 / 1 / 3 / 1 | 0 | 29 | 19 |
| Series C+D | 2 / **24** / 5 / 5 | 5 (+8) | 1 / 1 / 4 / 1 | **4** | **60** | **24** (16 with board requests) |
| Pre-IPO | 1 / 6 / 3 / 3 | 1 (+8) | 1 / 1 / 2 / 3 | 0 | 29 | 31 |
| **Total** | 6 / 54 / 17 / 18 | 18 (+28) | 3 / 6 / 20 / 8 | 4 | **182** | 20 (17 with requests) |

**Series C+D was 44 moments, one per 33 min. Three fixes (sim 9n, reference player):**
- **(a) Level I and II:** 12 upgrades become 24 levels at half price and half Income: 56 moments, 26 min.
- **(b) 4 valuation milestones** at 20 / 40 / 60 / 80% of the rung's valuation distance: decor piece, title, decor piece, one extra task tier (decor 22, titles 9 in all). They fire 7.1 / 12.3 / 16.6 / 20.2 h into the rung: 60 moments, 24 min.
- **(c) Board request every 45 engaged minutes, C+D only:** a `TaskConfig` row, choose 1 of 3, a **fixed 60 s of Income**, no random reward (**D9-safe**). 31 per rung: 91 moments, **16 min**; longest gap between events **45 min** (217 without requests).
- Hours to IPO 1 with the new items and all three: **57.1 h** (regular player), Series C+D 23.8 h.

**First 5.5 h (Garage + Seed) need:** 19 things to buy (9 exist today, re-priced), 4 tasks, 2 products, 7 decor, 2 titles: 36 moments, one per 9 min. Loops 2+ replay the ladder (an industry skin per IPO).

## 5. Shares, shop, and exactly what changes

`Shares = 20 x (1 + 0.25 x IPOs done) x min(ratio, 1.5) ^ 0.5` (was 10, 0.8, cap 2; x2 with the pass): 20, 25, 30 ... 65 per IPO; total 20 / 45 / 150 / 425 after IPO 1 / 2 / 5 / 10 (pass 40 / 90 / 300 / 850). Shop **750** (was 1,770): core 316 + cosmetic prestige wing 434.

**`IpoConfig`:** `SharesPerIpo` 10 to 20; `SharesGrowthPerIpo` 0.8 to 0.25; `SharesRatioCap` 2 to 1.5; perk costs (keys and levels unchanged) = `LONG_SHOP` in the sim, Night Shift `perLevel` 7,200 to **1,800 s** (base away cap 2 h in `TycoonCore`); `Stages` **5 to 7** (add `SeriesCD`, `PreIpo` before `IpoReady`); `StageGrowthPerIpo ^ L` becomes `StageScale(L) = (1 + 0.5 x L^0.75) x 1.05^L` for thresholds **and** every price; the IpoClient "wait longer" hint (cap 1.5). **`DailyConfig`:** Day 7 loses `shares = 3` (its egg = best tier already unlocked) and becomes a decor piece (decided; the piece joins in PR 4). **`OnboardingConfig`:** goal "Reach Seed" becomes "Buy 3 upgrades". **Tests:** of the 73 D1 checks about 28 hard-code old numbers and are rewritten (totals, level costs, Shares 10 / 0.8 / cap 2, stages 1800 ... 81000 x 2.5, both `IPO_PERK_COSTS` checks, two old-save checks); the other 45 stay. **Docs:** `ECONOMY.md` 3-3e, `D1_SHOP_OPTIONS.md`, PUBLISH_RULES 2, CLAUDE.md, ROADMAP; sim `IPO_*`. No real saves exist: levels only need clamping to `#costs`; after launch only add levels.

## 6. Money and passes

- **Shareholder pass (199 R$, 2001728902):** exactly **2x Shares**, plus the **Boardroom skin and a gold chat tag (`ChatTags`) at purchase**. Its only progress edge is speed perks 2 IPOs sooner: **about 13 h by IPO 6, still 13 h at IPO 10 (2%)** (the speed-Share Income is an estimate).
- **2x Cash pass:** valuation counts **base Cash** (doubled Cash would give owners IPO 1 in 28.6 h). At base: **48.7 h vs 57.1 h** (decided). **Cash packs** are gifts, never valuation.
- **Every `addEarnings` call and what it passes:** (1) TycoonCore income loop (`:733`): **base Income** (no 2x Cash or VIP, with the IPO multiplier), only while engaged; (2) TycoonCore offline block (`:692`): replaced by the away payout; (3) `ShopServer.lua:539` Cash packs: **call deleted**; (4) `IpoServer.addEarnings` (`:125`), the one choke point: new `kind` (`engaged`, `away`, `task`, `debug`) applies the 3 h/day weight and saves `away`; (5) Debug grants (`IpoServer.lua:404/411`): Studio only; (6) new `TaskServer`: Cash with passes, valuation at base (`kind = "task"` exists only from PR 2: until then tasks are Studio only, section 8); (7) `DailyServer` never calls it. The wrapper `TycoonCore.addEarnings` (`:478`) forwards `kind`.
- New products (fixed contents): Night Guard (8 h Poach Shield, 99 R$, `id = 0`), decor bundles. Never sold: stage skips, valuation, engaged-hour boosts, random boxes (D9).

## 7. New exploit: alt accounts feeding top hires

Kept employees carry over every IPO, so an alt that hatches Unicorn-tier eggs and "loses" them to a main account is now worth real hours. Sim (regular player; a fed hire is free):

| Case | IPO 1 | Loop 2 |
|---|---|---|
| no feeding | 57.1 h | 51.5 h |
| fed without limit, **no desk cap** | **27.1 h** | 22.1 h |
| R1 desk cap only | 45.3 h | 43.5 h |
| R1 + **at most 6 per run** / **3 per run** | 50.8 h / **53.3 h** | 46.5 h / 47.9 h |

**Rules:** R1 desk caps by office (a per-day limit never binds: desks open slowly); **R2 at most 3 poach-ins per account per run** (new section `lineage = { run = ipo.count, poachIns, poached = { [employeeId] = os.time() } }`, stale run = 0) and poach-won employees **do not carry over an IPO**; R3 poaching (either side) needs account age 14+ days and 10 engaged hours (not simulated). Three poach-ins leave the main 7% faster at IPO 1 (53.3 vs 57.1 h) and loop 2 within 4% (49.4 vs 51.5 h).

## 8. PR plan (order changed), gates

| PR | Content | Size | Gate / test |
|---|---|---|---|
| 1 | Task engine + customer calls **with measurement hooks** (ACTIVE doc 2, 5). **Adds the `tasks` save section (A10): Shut down all servers; rollback floor `V_launch`.** `addEarnings(kind)` arrives only in PR 2, so tasks run **in Studio only** (`TaskConfig.Enabled` and `RunService:IsStudio()`, like `DebugInStudio`) until PR 2 turns them on | L | daily_test; Studio |
| **G1** | **Studio playtest, calls only** (PR 1 has no other task): 5 players, 2 sessions each, 20+ engaged minutes per session, rung set by a Studio-only Debug "Set rung" button. Measured f = reward seconds / **engaged** seconds | | sim target (calls only): **Garage 0.32, Seed 0.37, Series A 0.41**. Pass: measured f within **0.8-1.2x** (0.26-0.38, 0.30-0.44, 0.33-0.49). Below: raise the call seconds; above: lower them; refit `f_mult` before PR 2. All-task values (0.32 / 0.50) are only the PR 2+ target |
| 2 | **Economy core:** base-Cash valuation, `kind` weights, engaged and away bank (`away`), `IpoConfig`, Daily Day 7, packs as gifts, sim and test sync. **Shut down all servers** | XL (may split) | new test groups; macro and bot in Studio |
| 3 | Desks, caps, kept-hire free refill, `lineage`, poach limits (`EmployeeServer`) | M | caps, 3 poach-ins, 2-client poach |
| 4 | Office framework, Seed, Daily decor piece | L | rung unlock, both phone sizes |
| 5-6 | Tasks 2-5 and rungs A, B; then C+D, Pre-IPO, roadshow, products | M each | grading, budget per rung, `id = 0` |
| 7 | Prestige wing, skins, industry skin 1, Investor Day | M | rule A10, pass skin |

**Order in TycoonCore:** `TaskServer` plugs in after `EmployeeServer` and `IpoServer`, **before `DailyServer`** (which stays last). **Stage to rung in PR 1** (5 stages until PR 2 adds `SeriesCD` and `PreIpo`): Garage 0, Seed 1, Series A 2, Series B 3, IPO-ready 4 (Series C+D budget); PR 2 swaps in the 7-stage mapping. Board request and milestones ship in PR 5-6.

## 9. Risks and decisions

Risks: retention over 100+ sessions, content volume, unmeasured Incomes and task bonus, a perfect task-bot (10.4 days); not simulated: fun, poaching, egg timers.

**Decided by the owner (closed):** Cash pass at base valuation; engaged cap 3 h/day then 5%; desk caps and 3 poach-ins per run; all rungs before launch; loop growth +5%; Day 7 Shares become a decor piece; paired demo and Investor Day outside the 50 h path. Open: none here (ACTIVE doc section 9).
