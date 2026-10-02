# D1: how big should the Shares shop be? (proposal; option C applied on branch launch-decisions)

Status: **option C (1,770 Shares) is applied** in `IpoConfig.lua` (branch `launch-decisions`, 2026-10-02), with `IPO_PERK_COSTS` in the sim, 146 new/extended checks in `tools/daily_test.py` and the docs updated. The text below is the original proposal and is kept as written (sections 5 and 6 say "I would change": that is now done as listed, including the optional `tools/daily_test.py` guard). Decision taken by Mattia: the Shareholder pass stays at `sharesMultiplier = 2` (a pass can't be weakened after people bought it), and the Shares shop gets bigger.

Numbers come from `tools/economy_sim.py --ipo --runs 40 --days 365` (the sim's own functions, 40 seeds, 365 days, daily calendar off, no perks). The shop is "bought" on the first day the player's total Shares earned reaches the shop size. Days are **real days** (wall clock) at the sim's session patterns: active = 3 x 20 min/day (1 h), casual30 = 4 x 72 min/day (4.8 h), casual = 1 x 10 min/day. The sim reproduces docs/ECONOMY.md for today's 525-Share shop (active 7 d no pass / 2 d pass, casual30 8 / 1, casual 20 / 6) and IPO timing (first IPO 12 min online, IPO 10 at 6.6 h), so the new numbers are comparable.

**Perks are not modeled.** Real players buy perks and are about 15-25% faster per IPO cycle. So real days are up to 20% fewer than the sim days below. Every target is therefore checked with a **25% margin**: a target of 28 days must show at least 35 sim days, 56 days at least 70.

## 1. Read this first

1. **A bigger shop does not bring the pass closer to "2x". It pushes it further away.** The pass gives exactly 2x the Shares at any date (day 7: 529 vs 1,060 for an active player; day 30: 721 vs 1,445; day 365: 1,063 vs 2,130, because the pass never changes when IPOs happen). But IPOs get about 2.3 times rarer each time (`StageGrowthPerIpo = 2.5`, Shares per IPO grow only linearly). Twice the Shares per IPO means about 3 IPOs fewer to reach the same total, and the last 3 IPOs take 10-50 times longer than the early ones. So "days to buy the whole shop" is 3.5x apart at 525 Shares (active), 13x at 800, 49x at 1,050, and a no-pass player doesn't finish at all in a year from about 1,100 Shares up.
2. **So these targets can't all hold at once with a size change alone:** "pass takes 4 weeks / 8 weeks" and "no pass about double". The first one needs a shop of about 1,700-1,800 Shares; at that size a no-pass player owns about 60% of it after a year.
3. **"active < casual30 < casual" can't hold either, but not because of the shop.** In the sim, `casual30` plays 4.8 h a day and `active` plays 1 h a day, so casual30 is the heavier player and is as fast or faster. The order that holds everywhere is {active, casual30} < casual. Don't read the name "casual30" as "plays less than active".
4. **Recommendation: option C, 1,770 Shares** (section 3), built as new levels on three perks that can't change IPO timing, with every existing level and cost left exactly as it is. It meets both pass-duration targets with the margin, keeps today's first 525 Shares at today's pace for everyone, and needs one Studio script (IpoConfig).

## 2. Days to buy the whole shop, with and without the pass

Median of 40 seeds. "x% / yr" = how much of the shop a no-pass player owns after 365 days. `>365` = not within a year.

| Size | active: pass / no pass | casual30: pass / no pass | casual: pass / no pass | Pass targets (35 d active, 70 d casual30, with margin) |
|---|---|---|---|---|
| **525 (today)** | 2 d / 7 d | 1 d / 8 d | 6 d / 20 d | fails both |
| **A: 1,050 (2x today)** | 6 d / 294 d | 8 d / >365 (98% / yr) | 20 d / >365 (92% / yr) | fails both |
| **B: 1,500 (about 3x)** | 54 d / >365 (71% / yr) | 41 d / >365 (69% / yr) | 136 d / >365 (64% / yr) | active yes, casual30 no (41 < 70) |
| **C: 1,770** | **125 d** / >365 (60% / yr) | **96 d** / >365 (58% / yr) | 309 d / >365 (54% / yr) | **both yes** |

Other sizes, same sim, active pass / no pass: 800 = 4 d / 54 d, 1,200 = 12 d / >365, 1,800 = 125 d / >365. The days move in steps because the shop is finished at an IPO, so **keep the total between 1,700 and 1,800**: a pass player needs IPO #14 there (casual30 and active alike), and at 1,850 casual30 jumps to IPO #15 (228 d), at 1,900 active does (293 d).

How the shop fills at C (share of the 1,770 Shares owned after N days, median):

| Player | Day 7 | Day 30 | Day 90 | Day 365 |
|---|---|---|---|---|
| active, no pass | 30% | 41% | 47% | 60% |
| active, pass | 60% | 82% | 94% | 100% (day 125) |
| casual30, no pass | 28% | 39% | 45% | 58% |
| casual30, pass | 57% | 78% | 90% | 100% (day 96) |
| casual, no pass | 18% | 31% | 42% | 54% |
| casual, pass | 35% | 63% | 84% | 100% (day 309) |

Read it like this: at every date the pass player has exactly twice the Shares (so the pass feels like 2x while you shop). The last 10-20% of the shop is a long tail that only pass players reach in the first months. Today's 525 stay as they are: no-pass players still buy them in 7-20 days.

What would give a real 2x on "days to finish" (not recommended now): make Shares per IPO grow geometrically instead of linearly. Same sim with Shares = `10 * g^IPOs`: g = 2 gives a whole-shop ratio of about 1.5-2x at any size (12,800 Shares: pass 6 d, no pass 12 d), g = 1.5 gives 2-5x (3,200 Shares: pass 12 d, no pass 54 d). It also means Shares per IPO in the thousands and every perk cost rescaled, so it rewrites the meaning of every saved Shares number. Too big a change for the launch; keep it as an idea for later.

## 3. The three options

All three keep **every existing level and cost** (the 25 levels, 525 Shares), so a save that already owns perks loads exactly as before. They only add levels at the end of three perks. Costs rise about 1.4-1.5x per level.

Option C (recommended), the only one I'd build:

| Perk | Existing costs (unchanged) | Added levels | Effect of the added levels |
|---|---|---|---|
| FasterEggs | 5, 10, 20, 35, 50 | **90, 140** (levels 6-7) | -60% and -70% hatch time (cap at -70%, see section 4) |
| BaseLuck (Talent Scouts) | 5, 10, 20, 35, 50 | **80, 120, 175** (levels 6-8) | +60%, +70%, +80% odds weight of Rare/Epic/Legendary |
| CheaperPoach | 5, 10, 15, 20, 25 | **50, 75, 110, 165, 240** (levels 6-10) | -30% ... -50% poach cost |
| **Added Shares** | | 230 + 375 + 640 = **1,245** | |
| **Shop total** | 525 | | **1,770** |

A (1,050) and B (1,500) are the same idea with fewer added levels (+525 and +975 Shares); I did not draw their cost tables because I don't recommend either.

If you don't want to extend Talent Scouts (see section 4), take its 375 out of C: the shop is then 1,395, about option B without the casual30 target. Going beyond about 1,800 with config alone isn't possible, because only these three perks are safe to extend. More than that needs **new perks with new code** (a title or cosmetic badge in IpoServer/IpoClient).

## 4. Checks (what a bigger shop touches)

| Area | Result |
|---|---|
| **IPO timing** (first IPO about 12 min active, IPO 10 about 6.6 h) | **Unchanged.** Stages, `StageGrowthPerIpo`, the Shares formula and `Resets` are not edited. The sim re-run with the real values still gives 12 min and 6.6 h. The shop size only decides how fast Shares are *spent*, not how fast they arrive. |
| **Shares formula** (`SharesPerIpo` 10, growth 0.8, cap 2, exponent 0.5) | Unchanged; the pass multiplies the result by 2 exactly as today (IPO 1 = 10 / 20 Shares, IPO 4 with the pass = 68). |
| **FasterEggs** | Safe: `math.max(0, 1 - perk)` on the server (EmployeeServer `startEgg`) and the same formula in EmployeeClient. Keep the total at -70% or less: at -90% the Instant Hatch product (25 R$) is worth almost nothing. |
| **CheaperPoach** | Safe: floor `math.max(0, 1 - perk)` in PoachServer. -50% is the most I'd allow (cheap poaching vs the "poaching must never feel crushing" rule). |
| **Talent Scouts (BaseLuck)** | Works (weights scale as `1 + 0.1 x level`, and the fixed hire order for restricted players follows the same weights). The description text says "+10% per level", which stays true because it comes from `perLevel`. Two flags: levels 6-8 change the hire odds (more Rare/Epic/Legendary, so slightly more income); and Shares bought faster with the Robux pass buy an odds modifier, so re-read the Paid Random Items policy again before launch (ROADMAP before-publish item i). If that worries you, skip this perk (see above). |
| **ExtraIncubator, ExtraSlot, OfflineCap** | **Do not extend.** ExtraIncubator: EmployeeClient builds its incubator row from `#costs` and every incubator is a plot object. ExtraSlot: one employee is up to +175 income/s, so it speeds every IPO. OfflineCap: offline Cash counts as valuation, and the sim shows offline Cash is what clears the IPO thresholds, so more offline hours speed every IPO. None of these is in the sim, so the margin would be eaten. |
| **IPO screens** | Data-driven: IpoClient draws one card per `IpoConfig.Perks` entry, "Lv n/max" and the next cost come from `#costs`, effect text from `perLevel`. Costs up to 240 should fit the 92 px phone button (`📜 240`), "Lv 10/10" the name line, and the Shares HUD `📜 n` with up to 4 digits (not tested in Studio). No IpoClient code change; check the Shares Shop page on a phone. The IPO confirm screen and the "Wait longer for more Shares" hint don't use the shop total (hint reword is D2, separate). |
| **Saved Shares and perk levels** | Safe. `ipo.shares` is a plain number; `ipo.perks[key]` is clamped to `#costs` on load (IpoServer.lua:365), so a level that was valid stays valid and a perk at its old max (5/5) gets a buy button for level 6. No new field, no new section, no save-format change. Debug tools (IpoGrantShares, IpoReset) have no perk maximum in them. |
| **Rollback** (docs/PUBLISH_RULES.md section 2) | Build this **before launch**, so the launch version already has it. After launch, a rollback to a version with fewer levels clamps levels 6+ back to 5 and the Shares spent on them are gone. Same family as rule A10, but the new values are inside an existing field, so it is a one-way change: forward only. |
| **Tests** | At proposal time `tools/daily_test.py` had no check on perk costs and its Talent Scouts tests stopped at level 5 (+50%). Now built: the odds and fixed-order checks also run every egg at Talent Scouts level 8 (+80%) with and without Luck Boost (still exactly 100.00%), and a new IPO shop block runs the real IpoServer with fakes (71 checks). |

## 5. Files and numbers I would change if you say yes

| File | Change | Studio script? |
|---|---|---|
| `IpoConfig.lua` | `Perks[FasterEggs].costs = {5, 10, 20, 35, 50, 90, 140}`; `Perks[BaseLuck].costs = {5, 10, 20, 35, 50, 80, 120, 175}`; `Perks[CheaperPoach].costs = {5, 10, 15, 20, 25, 50, 75, 110, 165, 240}`. Nothing else: no `perLevel`, no key, no existing cost, no Shares formula number. | **Yes: `IpoConfig` (ReplicatedStorage), the only one.** Server and client both read it, so no IpoServer / IpoClient / EmployeeServer / PoachServer paste. |
| `tools/economy_sim.py` | `IPO_PERK_COSTS` (lines 116-119): same three arrays, so the printed shop total becomes 1,770. | No (repo only) |
| `docs/ECONOMY.md` | Section 3d: replace the "Decision needed before launch" paragraph with the decision, and update the "Shop pace" table with the new total (new run, section 2 of this file). Sections 3b/3c stay as history. | No |
| `ROADMAP.md` | D1 line in "Open launch decisions" (mark done) and the M9 line "decide Shareholder pass strength vs shop size". | No |
| `docs/PREPUBLISH.md` | Row D1 (mark decided). | No |
| `tools/daily_test.py` (optional) | A small guard: every perk's costs strictly rise, and the first 5 costs of each perk equal today's, so a later edit can never change a shipped level. | No |

**Not touched:** `ShopConfig` (pass stays `sharesMultiplier = 2`, no pass or product ID), `IpoServer`, `IpoClient`, `EmployeeServer`, `EmployeeClient`, `PoachServer`, `TycoonCore`, `ShopServer`, `CreatureConfig`, the save format and `KNOWN_SECTIONS`. Claim `IpoConfig`, `tools/economy_sim.py`, `docs/ECONOMY.md`, `ROADMAP.md`, `docs/PREPUBLISH.md` (and `tools/daily_test.py` if the guard is added) in CONTRIBUTING.md first.

After the edit: paste IpoConfig into Studio, playtest (F5): Shares Shop tab shows Lv x/7, x/8, x/10; with Debug "Grant Shares" buy the new levels; Talent Scouts text shows +60%...; rejoin keeps the levels; check the phone layout of the Shares Shop. Run `python3 tools/daily_test.py` and the sim (`--ipo --runs 40 --days 365`) again.

## 6. Recommendation

**Option C, 1,770 Shares**, with the cost table above. Why:

- It is the only size that meets the pass targets with the 25% margin (125 d active, 96 d casual30), and it sits in the middle of the 1,700-1,800 step, so small cost edits don't move the result.
- Nothing a player already has changes, and the first 525 Shares come at the same pace for everyone, so a no-pass player's early game is untouched.
- The added levels are on perks with no effect on IPO speed, plot objects or the sim's numbers (FasterEggs, CheaperPoach, Talent Scouts), so the IPO timing in docs/ECONOMY.md stays true.
- The pass stays exactly 2x in Shares at every date. What changes is the tail: only pass players finish the shop in the first months. Say so in the store text ("2x Shares") and don't promise more.

Honest limits: no-pass players never finish the shop in the first year (about 55-60% owned), the "pass = about 2x in days to finish" target isn't reachable with a bigger shop, the active/casual30 order can't be forced (section 1), and everything here is a sim without perks. If you'd rather keep a free player able to finish, option A (1,050) does it in about 10 months for active, but then a pass player finishes in about a week.

## 7. Reproduce

```python
# from the repo root; does not edit anything
import sys, statistics; sys.path.insert(0, "tools")
import economy_sim as e
def days(behaviour, pass_on, size, n=40):
    out = []
    for seed in range(n):
        r = e.run(behaviour, seed, days=365, use_ipo=True, shareholder=pass_on)
        total, when = 0, float("inf")
        for gained, t in zip(r.shares_log, r.ipo_times):
            total += gained
            if total >= size:
                when = t / 86400
                break
        out.append(when)
    return statistics.median(out)  # inf = not within 365 days
print(days("active", True, 1770), days("active", False, 1770))
```
