# Long game: the IPO is the last thing (proposal, design only)

Branch `active-loops`; no game code, no `IpoConfig` or perk number changed. Direction from the owner: first IPO after **50+ active online hours**, every later loop 50+ h, tasks are the core. This **supersedes** the pacing and Shares parts of `docs/ACTIVE_LOOPS_PROPOSAL.md` (section 3 and question 1; its engine, task table and safety stay) and `docs/ECONOMY.md` sections 3-3e. Numbers come from `python tools/economy_sim.py --long --runs 40` (section 9). "Active hour" = online and answering tasks. Decided earlier and kept: calls pay 7 s of Income, task Cash counts toward valuation, the Cash pass multiplies task Cash, pitch Shares are never doubled, Investor Day prizes are cosmetic.

**Principle: Cash can only fill a rung, never skip it.** Each rung has an income ceiling and a valuation threshold. Money (packs, passes, away pay) buys things sooner inside a rung; only active play moves the clock.

## 1. Pacing

First IPO **57 active hours** for the typical player (target 55-60; an expert at tasks 55). Later loops: prices and thresholds grow **+5% per loop**: loops 57 / 57 / 58 h, IPO 10 at 607 h in total (about 61 h each). Flat (+0%) shrinks to 53 h by loop 3 (kept team, perks); +10% reaches 64 h by loop 3 and keeps rising. Same ladder every loop, kept employees only make the early rungs faster.

| Player (sim) | Active h/week | IPO 1 | IPO 2 | IPO 5 | IPO 10 |
|---|---|---|---|---|---|
| dedicated (2 h/day) | 13 | 57 h, **4 wk** | 9 wk | 22 wk | 46 wk |
| regular (1 h/day) | 6.4 | 57 h, **9 wk** | 18 wk | 46 wk | 97 wk |
| casual (3 x 1 h/week) | 2.5 | 57 h, **23 wk** | 45 wk | 114 wk | 238 wk |

A casual player sees a rung every 2-6 weeks and about 3 unlocks per 1-hour session. Honest: casual IPO 1 is 5 months; casual IPO 10 is 4.6 years, so casual players are served by rungs, titles and the leaderboard, not by IPOs.

## 2. The stage ladder (the spine)

7 rungs + IPO-ready (Garage, Seed, Series A, B, **C, D, Pre-IPO** are new; 8 entries in `IpoConfig.Stages` instead of 5). Valuation to enter the next rung (loop 0 prices) and hours from the calibrated sim; a reward moment (new office, hire type, task, product, upgrade, decor, title) every **12-29 min**, faster early (12 in the first 90 minutes).

| Rung | Hours in rung (cum.) | Enter next at | Income ceiling /s | Moments (min each) | New this rung |
|---|---|---|---|---|---|
| Garage | 1.5 (1.5) | $32K | 6 | 12 (8) | calls; today's 6 upgrades, 3 hires, Garage egg |
| Seed | 4 (5.5) | $362K | 20 | 20 (12) | office 2, bugs, features, interview, Startup egg, 1 product |
| Series A | 6.5 (12) | $2.6M | 65 | 24 (16) | office 3, pitch, events, demo, new egg, 2 products |
| Series B | 9 (21) | $13.8M | 210 | 27 (20) | office 4, press, ads, crisis, Unicorn egg |
| Series C | 11 (32) | $61.7M | 700 | 28 (24) | office 5, launch, paired demo, new egg |
| Series D | 13 (45) | $253M | 2,300 | 29 (27) | office 6, 3 products, new egg |
| Pre-IPO | 15 (60) | $982M | 7,500 | 31 (29) | office 7 (HQ), roadshow, 4 products |

**Content to fill one loop (171 moments, 21 min each):** 6 offices, 42 office upgrades (6 per office), 25 hire types, 6 egg tiers, 20 tasks, 14 products, 50 decor pieces, 8 titles. **Exists today: 20 (12%)**: 6 upgrades, 11 hires, 3 eggs. **Missing 151:** all offices after the garage, 36 upgrades, 14 hire types (income up to ~600 each: today's best is 175 and 8 slots cap income near 1,400; the ceilings need ~20 desks), 3 egg tiers, all 20 tasks (designed, 0 built), 14 products, 50 decor, 8 titles. Loops 2+ replay the ladder: add one **industry skin** per IPO (office theme, 4 hires, 1 task flavour, titles); honest: after loop 2 the pull is leaderboard, poaching and Investor Day more than content.

## 3. Offline and idle: active hours are the gate

**Rule:** after 3 minutes without a valid input the startup is *away* (also while the app stays open, so AFK does not farm). Away pay = **10% of the active pay you left with**, banked up to **2 h per return** (Night Shift +30 min per level, to 4 h), spendable at once, but **only 10% of it counts toward valuation**. Cash packs and daily Cash never count (gifts). Tasks, auto-resolve and chains pay nothing away.

| Rule (regular player) | Active h to IPO 1 | Valuation from away | Check-in only (1 min/day) |
|---|---|---|---|
| none | 60.0 | 0% | never |
| **proposed** (10% pay, 2 h, 10% counts) | **57.3** | 2% | never in 3 years |
| 25% counts | 55.9 | 5% | 14.9 h, 133 wk |
| **today** (50% passive, 8 h, 100% counts) | **20.0** | 69% | 0.6 h, 5 wk |

Today's rule would give IPO 1 after 20 active hours and let a 1-minute-a-day player in 5 weeks. "Come back and see progress" stays: the bank, hatched eggs and a stage bar that moves a little. **Daily calendar:** Cash days stay a gift; eggs come only from tiers already unlocked (no skipping); **Day 7 loses its 3 Shares**: 3 a week is 27 Shares over a regular player's 9 weeks to IPO 1, more than the IPO pays (20). Swap for a decor piece.

## 4. Shares and the shop

Formula keeps its shape: `Shares = 20 x (1 + 0.25 x IPOs done) x min(ratio, 1.5) ^ 0.5` (was 10, 0.8, cap 2; x2 with the pass). Per IPO 20, 25, 30 ... 65 at IPO 10; total 20 / 45 / 150 / 425 after IPO 1 / 2 / 5 / 10 (pass: 40 / 90 / 300 / 850). Shop **750 Shares** (was 1,770): core 316 (same six perks, keys and levels, re-priced) + a new **prestige wing 434** (office skins, creature hats, titles; cosmetic). Speed perks (FasterEggs, ExtraIncubator, ExtraSlot, BaseLuck) cost 154 together and are worth at most about +25% Income (estimate, not simulated).

| After | Shares (pass) | What you own (cheapest levels first) |
|---|---|---|
| IPO 1 | 20 (40) | hatch -30%, luck +30%, Night Shift 1, poach -10% (pass: + incubator, desk) |
| IPO 2 | 45 (90) | hatch -40%, luck +40%, +1 incubator, +1 desk, Night Shift 2, poach -15% |
| IPO 5 | 150 (300) | speed perks nearly done (pass: all, IPO 4); Night Shift 4h, poach -30% |
| IPO 10 | 425 (850) | core done (IPO 9; pass IPO 6), 110 Shares into the wing (pass: wing done, IPO 10) |

Whole shop: IPO 15 without the pass, IPO 10 with it. Costs (core): FasterEggs 1,2,3,5,7,10,16; Incubator 4,8; Desk 4,8,18; Scouts 1,2,3,5,7,10,16,24; Night Shift 2,4,7,12 (+30 min each); Poach 2,3,4,6,8,11,15,20,28,40. **Must change:** `IpoConfig` (SharesPerIpo, growth, cap, `Perks` costs, OfflineCap `perLevel`, Stages 5 to 8 with new keys `SeriesC`, `SeriesD`, `PreIpo` before `IpoReady`, `StageScale(L) = multiplier(L) x 1.35 x 1.05^L` replaces `StageGrowthPerIpo ^ L` for thresholds and prices); sim constants (`IPO_*`, `IPO_PERK_COSTS`); `tools/daily_test.py` (the 73 shop checks assume 1,770; stage and Shares checks); docs (ECONOMY, CLAUDE.md save notes, ROADMAP, D1_SHOP_OPTIONS); the IpoClient "wait longer" hint. Re-pricing is safe **only before launch** (nobody holds real perks); after launch add levels only.

## 5. Monetization

- **Shareholder pass (199 R$, id 2001728902):** stays exactly 2x Shares, never reduced. At the new pace it is +20 Shares every 57 h, felt on every IPO. It never touches the clock. The only progress edge is that speed perks arrive 2 IPOs sooner (IPO 4 vs 6, about 115 active hours earlier, worth roughly 10-15 h across those loops): small by design because the speed tier is cheap (154). Keep value with cosmetics, not power: a Shareholder Boardroom skin and gold chat tag (`ChatTags`), plus the prestige wing finishing 5 IPOs sooner.
- **2x Cash pass:** it must **not** double the valuation: if it does, owners reach IPO 1 in **28.7 h** (sim), breaking the 50 h rule for everyone who pays; with valuation at base Cash it is **55.4 h vs 57.3 h**. The pass then buys things sooner and feeds Cash sinks (decor, skins), not the clock. Revenue risk, see question 1.
- **Cash packs:** gifts, not valuation (today `ShopServer.lua:539` counts them; the Vault is 3 h of income).
- **Poach Shield (49 R$, 1 h):** unchanged. Kept employees are the carry that speeds every loop, so the shield matters more; add **Night Guard 8 h, 99 R$** (id 0, owner runs the sync).
- **New products** (cosmetic, fixed and shown contents): decor bundles, Boardroom skins. Never sold: stage skips, valuation, active-hour boosts, mystery boxes. **D9:** nothing sold for Robux is random; random hires keep `isRandomRestricted` and the fixed order.

## 6. Tasks across 50 hours

Rewards are seconds of Income, so they grow with the rung (cost of nothing extra). The sim's task bonus is **x1.34 in the Garage, x1.71 by Series A, x1.84 at Pre-IPO**: at hour 40 tasks are still about 45% of what an active player earns. To stay interesting: (1) a new task family every ~3 h (1, 3, 4, 4, 4, 3, 1 per rung = 20), each with 3 tiers (more options, tighter limits, same seconds-based reward); (2) an **exception** per rung that employees can never take (pitch, crisis, press, roadshow); (3) difficulty `level = rung + min(IPOs, 10)`, arrival rate cap x1.4, unchanged budget 0.85 s of Income per online second (so x1.85 is the ceiling and a bot gains nothing); (4) **no penalty for hiring:** demand per hire is capped (`D = min(2.0, 1 + demand x hires)`), employees auto-resolve up to 75% of routine tasks, and the founder keeps at least 25% of the calls, so a 20-desk team gets more handled calls, not more work. Not measured: the sim's rosters stop at 8 hires, so founder load with 20 hires is untested (first Studio check of PR 3).

## 7. Sim (`--long`, default OFF)

Default, `--ipo`, `--daily`, `--active` outputs are byte-identical to before (checked with `cmp`); `daily_test.py` **658 passed, 0 failed**. The model is a calibrated ladder: thresholds are read off a reference player so the regular player hits 55-60 h **by construction**. What the sim does show: the other players, the away rules, the pass effect, loop growth and the Shares curve. **It cannot measure:** fun, content existing, retention, real 20-desk Income, poaching, luck and egg timers (a +25% perk lump instead), longer sessions, people (friends, leaderboard pull).

## 8. Risks (five biggest)

1. **Retention over 100+ sessions.** Most players will leave long before hour 57; only a minority will get there. *Design:* 12 moments in hour 1, a moment every 21 min, a rung every 2-6 weeks even for casual, a title and a cutscene per rung, weekly Investor Day.
2. **Content volume:** 151 of 171 moments do not exist; loops 2+ replay them. *Design:* launch with rungs Garage-B (21 h) and ship one rung every 2 weeks (a regular player reaches rung C in week 4); industry skins per loop; decor via a counter, not new systems. Honest: this is months of work.
3. **The grind in hours 20-45** (item payback 9-11 h). *Design:* event and exception tasks, the decor Cash sink, ceilings that make each rung feel new. Unknown until played.
4. **Pay-to-win and pass trust.** *Design:* valuation at base Cash, packs as gifts, the clock never sold, Shareholder power perks cheap (154).
5. **"Active" detection and exploits** (AFK tabs, autoclickers, honest players marked away). *Design:* 3-minute input rule shown on the HUD ("Away: tap to resume"), 0.85 s budget, reaction flags, rate limits from the active-loops doc.

## 9. Work already merged, and the PR plan

**Impact:** D1 shop (1,770, 73 checks) replaced by 750; IPO retune (Seed $1,800, x2.5, IPO in 12 min) replaced by 8 rungs and `StageScale`; daily reward loses Day 7 Shares and gives only unlocked eggs; Cash packs and the Cash pass change valuation rules; onboarding goal "Reach Seed" moves to 1.5 h; dev saves with old valuations just land on a lower rung (no real saves exist before launch).

| PR | Content | Size | Test plan |
|---|---|---|---|
| 1 | Economy core: `IpoConfig` stages, Shares, shop, `StageScale`; valuation at base Cash; packs as gifts; sim and test sync | L (500 Lua + 300 test) | `daily_test` new groups: shop 750, `sharesFor`, thresholds, old save loads; Studio: IPO at Debug valuation |
| 2 | Engaged flag + away bank, "while you were away" (M6b) | M (450) | no input 3 min, cap, 10% valuation, rejoin |
| 3 | Task engine + calls (active-loops PR 1) | L (1,100 + 250) | as in the active-loops doc |
| 4 | Office framework (`OfficeConfig`, ceilings, unlock by rung) + Seed, Series A | L (1,200) | rung unlock, both phone sizes |
| 5 | Tasks 2-5 and rungs B, C (per active-loops PRs 2-4) | M each (450-600) | grading, boost cap, Shares slot |
| 6 | Daily changes (Day 7, unlocked eggs) | S (120) | claim tests, no double claim |
| 7 | Rungs D, Pre-IPO, roadshow, products (Night Guard, decor) | M each | once per run, `id = 0` |
| 8 | Prestige wing, skins, industry skin 1 | M (500) | save section (rule A10), pass skin |

Each PR re-runs the sim and updates this doc's table; PR 1 needs **Shut down all servers** only if a save section is added (none here).

## 10. Questions for you (recommended numbers first)

1. **Cash pass x2 and the clock:** valuation at base Cash (recommended; owners IPO in 55.4 h, the pass sells faster buying and Cash sinks) or doubled (28.7 h, breaks the rule). Revenue risk is yours to weigh.
2. **Launch scope:** launch with 21 h of rungs (Garage-B) and add a rung every 2 weeks (recommended), or hold the launch for all 60 h?
3. **Loop growth** +5% per loop (recommended; 57-62 h per loop) or flat; the visible IPO multiplier then only sets the size of numbers: OK?
4. **Daily Day 7:** drop the 3 Shares for a decor piece (recommended) or keep 1 Share?
5. **Away rule:** 3 minutes without input, 10% pay, 2 h cap, 10% valuation (recommended), or a gentler 5 minutes?
