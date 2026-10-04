# Funding rounds (proposal, design only)

Design only (2026-10-05, branch `design-customize`): owner decision **D-F**, split out of docs/CUSTOMIZE_PROPOSAL.md (`CUST` below). No script, config or test changed. For the owner and the Claude sessions that will build it. Line numbers are for this branch after merging `main` `9798388`. **(unverified)** = not checked in code; **(estimate)** = not measured; **(placeholder)** = sized by the sims. The saved fields (`pokedex.active.told`, `rounds`; `card.rounds`, `stake`, `shares`), the `pokedex` loader, versioning and the run check stay in CUST 1.2; the module names (`CompanyServer`, `CompanyConfig`, `CompanyClient`, `CompanyRemotes.CompanyAction`) in CUST's "New names".

**Fixed by the owner:** **D-F** reaching a stage by valuation lets the player raise a round of a size they pick; it gives Cash only, costs dilution (fewer IPO Shares), and the room follows the building owned, not the stage (CUST 6). **Round Cash path (decided 2026-10-05):** paid like the daily gift: spendable Cash, valuation unchanged, never through `addEarnings` (DailyServer.lua:177-180; test daily_test.py:110).

## 1. The rules

Every number is a **placeholder** for S8 (section 6); nothing is random (D9).
- **What opens a round:** the **valuation** (never Cash) reaching a stage after the first: Seed, Series A, Series B today (IpoConfig.lua:17-23), plus Series C+D and Pre-IPO with LONG_GAME's 7 stages. IPO-ready has no round: it is the IPO. The stage is `IpoConfig.stageIndex(ipo.valuation, ipo.count)` (IpoConfig.lua:151-159); it never falls during a run (IpoServer.lua:122-135).
- **A round gives Cash and nothing else:** no building move, no Income change. The stage's building is buyable in SHOP > Office once the stage is reached, raised or not; the room follows the building owned (CUST 6). The Cash buys anything.
- **Flow:** (1) stage reached: one message per stage per company (`told`); the valuation bar reads "Raise a round ›" while a round is open (section 5). (2) The **Funding window**: 3 choices (Small, Medium, Large), each with its Cash, the share given away, the IPO Shares after it and the stake left; a choice that would take the total past the cap is locked. (3) **Raise** (pick, then confirm "Raise $X for Y%"): Cash at once. **Later** keeps the round open. **Skip this round** (with a confirm) closes it for this company.
- **One round per stage per company,** settled in stage order; an open round stays open at the next stage; all close at IPO-ready (raised Cash could then only feed the seed). **Never raising** is a full path: no dilution, all the Shares, "Bootstrapped: 100% stake" on the card, no extra reward.
- **Amount:** choice i gives `floor(IpoConfig.stageValuation(roundStage, ipo.count) x cashBp[i] / 10000)` (IpoConfig.lua:140-143; `cashBp` whole, 1,000 / 2,000 / 3,000): the **round's own stage**, never the stage the player is at when raising, and the IPO count (fixed during a run: rounds close at IPO-ready). Its dilution is that stage's row of section 3's table too. Never Cash, Income, passes or stamps. *Test:* a Seed round left open and raised at Series B pays the Seed amount and costs the Seed bp. **Cash packs** call `addEarnings` today (ShopServer.lua:540), so they open a round sooner, never a bigger one (the amount reads only the stage and the count); after LONG_GAME PR 2 they are gifts (LG:93-94) and open nothing, and rounds go live only after it (section 7). Placeholders: 10 / 20 / 30% of the stage's threshold; the dilution of each choice at each stage comes from section 3's curve (whole bp, a table); **total dilution capped at 4,000 bp** (`DilutionCap`): a raise that would take the total past it is refused. Income is untouched. Data: `CompanyConfig.Funding` (shared engine, keyed by `IpoConfig.Stages` keys), `Enabled`, `StudioOnly`.
- **Saved** (`pokedex.active`): `told[stageKey]`; `rounds[stageKey]` = `s`, `c` (choice), `cash`, `bp` (dilution in basis points, whole, 0-10000, **as applied**, never recomputed from a later config), `at`, `studio`. `D = min(DilutionCap, Σ bp)` in whole bp, derived on load. A round under an **unknown stage key** is kept and its valid `bp` still counts (a newer version's round dilutes an older version's IPO). A malformed record of a known stage counts as settled with `bp` 0 and a warning, never dropped (that would allow a second raise).
- **The card keeps** `rounds` as they were, `stake` (10000 - D in bp) and `shares` (paid after dilution and pass): "Founder stake 70% · 3 rounds · $X raised" or "Bootstrapped".

## 2. Cash, valuation, Shares

- **Not an `addEarnings` call (owner decision, 2026-10-05).** Every `addEarnings` raises valuation, lifetime and best (IpoServer.lua:123-135, via TycoonCore.lua:591-593), so a round paid through it *is* the loop round → valuation → next round. Decided: a **Cash grant** like the daily calendar (DailyServer.lua:174-180) in one function, **`CompanyServer.raiseRound`**, with an after-check like Daily's (valuation and lifetime unchanged, else "BUG", :195-200), extended to `best`. A check allows exactly one `cash.Value +=` in CompanyServer, inside `raiseRound`.
- **Tests that protect the valuation** (a plan for PR 4b; daily_test.py is not edited here). Today's call-site check (daily_test.py:4536-4543) only reads the 8 files named in `expected` (:4537), so a new `CompanyServer.lua` would go unchecked, and its regex `addEarnings\s*\(` misses an alias (`local pay = core.addEarnings` then `pay(player, n)`). The PR adds:
  - **(a) Every `.lua` file.** The check loops over every `.lua` file at the repo root (like the `Touched` check, :4462-4465); a file missing from `expected` must have 0 calls. Every other mention of the word `addEarnings` in code (not a call, not a `function ...addEarnings(` line) must match an allow-list: today only TycoonCore's two table fields `addEarnings = addEarnings,` (TycoonCore.lua:626, 676). An alias, `core["addEarnings"]` or a pass-along then fails. `CompanyServer.lua`: the word appears 0 times, in any form.
  - **(b) No `addEarnings` in CompanyServer's core table.** The text of `CompanyServer.init({ ... })` in TycoonCore holds no `addEarnings`, like `DailyServer.init` (TycoonCore.lua:685-690, which gets only `getData` and `save`); the same check is added for `DailyServer.init`.
  - **(c) No direct write outside IpoServer.** In every `.lua` file but IpoServer, no assignment to `.valuation`, `.lifetime` or `.best` (`=`, `+=`, `-=`, also inside a multiple assignment). Allow-list: `daily.best` in DailyServer.lua:192, 275, 333 (the streak record, not the IPO). IpoServer's own writes are pinned by count (:129-131, 231-232, 356-358, 372, 426), so a new write there fails too.
  - **(d) A runtime Raise with the real code.** CompanyServer runs against fakes like daily_test.py:63-66: a fake `IpoServer` with no `addEarnings` (a call would error) and a core table without it. For each choice and each round stage: Cash rises by exactly `CompanyConfig`'s amount (section 1); `ipo.valuation`, `lifetime` and `best` are unchanged (like daily_test.py:110); no "BUG" warning; a second `Raise` of the same round changes nothing.
- **Validation:** `CompanyAction("Raise", round, choice)`: `round` = the stage number the window shows, an anti-replay token like `ipoNumber` (IpoServer.lua:179); `choice` a whole number 1..#choices; no amount is read. No yield between check and write (DailyServer.lua:146-149). Refused unless: funding active (`Enabled` and (`StudioOnly` off or Studio)); `data.ready` (false while loading and while an IPO saves, IpoServer.lua:212-213); `round` = the earliest open round; the choice fits under the cap; 1 Raise per 2 s (like `BUY_MIN_INTERVAL`, TycoonCore.lua:239). Record and Cash change together, then `core.save` (a failed one leaves both for the next save). **One claim per stage** = the record. **No replay:** a stale `round` is refused; a rejoin loads the record; Cash and record share one payload and key (TycoonCore.lua:421-433, 505), so a lost save or a restored version drops or keeps both.
- **Out of the valuation, in code.** Valuation changes only in `IpoServer.addEarnings` (:129), `goPublic` (:231), setup (:356) and Debug (:403, 410, 426). The earners read **Income, not Cash**: the income loop passes `stats.Income.Value` (TycoonCore.lua:865-866), offline pay is `away x income.Value x OFFLINE_RATE` (:819-827), `baseIncome` is `totalIncome x IPO multiplier` (:677-680, from `owned` and employees, :137-145). Raised Cash reaches the valuation only through items that raise Income: the intended time saving, which can't compound because a round's size comes from config and the stage. Same after LONG_GAME PR 2 (base Cash, LG:93).

## 3. Shares and dilution

**Why a fixed price fails.** A fixed 3 / 7 / 12% at every stage ignores that the Cash (`cashPct x stageValuation`) grows about 4,750 times from Seed ($197K) to Pre-IPO ($937M) on LONG_GAME's ladder (LG:42-47). Against the stage's **gap** (the valuation still to earn before the next stage), a Large round is worth 0.94% at Seed, 6.29% at Series A, 9.74% at Series B, 5.85% at C+D and 30.46% at Pre-IPO, always for 12%; today's 5 stages give 12.00 / 11.05 / 12.19%. Nobody should raise at Seed, everybody at Pre-IPO.

**The curve: the price follows the time a round is worth** (every number a **placeholder** for S8):
- `g` = the round's Cash / the stage's gap = `cashPct x stageValuation(s) / (stageValuation(s+1) - stageValuation(s))`. Both ladders scale every threshold by one factor per IPO (IpoConfig.lua:140-143; LG:88), so `g` doesn't depend on the IPO count.
- `h` = the stage's share of the loop's engaged hours: data, `Funding.HoursShare[stageKey]`, from LONG_GAME's rung hours (LG:42-47, loop 59.8 h) or today's first run (Seed, Series A, Series B last 2, 1, 5 of 12 minutes; ECONOMY.md 3b) until S8 measures them.
- `u = g x h`: the round's Cash in loop time at that stage's earning rate. An upper bound on the time saved: the Cash never counts toward the valuation, it only buys Income sooner.
- `bp = max(1, floor(P x u x 10000))`, with `P` = 1.5 / 2.0 / 2.5 (Small / Medium / Large): % of Shares given per % of loop time.
- The bp are **whole numbers in a table** in `CompanyConfig.Funding` (written from S8, never computed with floats at run time: today's Seed Large is exactly 500 bp, but floats give 499). A test recomputes the table with exact fractions.

| LONG_GAME (7 stages) | Gap share S / M / L | Loop time (L) | bp S / M / L |
|---|---|---|---|
| Seed | 0.31 / 0.63 / 0.94% | 0.063% | 3 / 8 / 15 |
| Series A | 2.10 / 4.19 / 6.29% | 0.684% | 34 / 91 / 170 |
| Series B | 3.25 / 6.49 / 9.74% | 1.466% | 73 / 195 / 366 |
| Series C+D | 1.95 / 3.90 / 5.85% | 2.330% | 116 / 310 / 582 |
| Pre-IPO | 10.15 / 20.30 / 30.46% | 7.639% | 381 / 1,018 / 1,909 |
| **Every round** | | **12.18%** | **607 / 1,622 / 3,042** |

| Today (5 stages) | Gap share S / M / L | Loop time (L) | bp S / M / L |
|---|---|---|---|
| Seed | 4.00 / 8.00 / 12.00% | 2.000% | 100 / 266 / 500 |
| Series A | 3.68 / 7.37 / 11.05% | 0.921% | 46 / 122 / 230 |
| Series B | 4.06 / 8.12 / 12.19% | 5.078% | 253 / 677 / 1,269 |
| **Every round** | | **8.00%** | **399 / 1,065 / 1,999** |

*Worked:* Pre-IPO Large: `g = 0.30 x 937M / (1,860M - 937M) = 30.46%`, `h = 15.0 / 59.8 = 25.08%`, `u = 7.639%`, `bp = floor(2.5 x 763.9) = 1,909`. Today's Seed Large: `g = 540 / 4,500 = 12%`, `h = 2 / 12`, `u = 2%`, `bp = 500`. Large every round saves at most 12.18% / 8.00% of a loop (S8 mark: ≤ 15%) and costs 30.4% / 20.0%: under the cap.

**No choice is dominated, at any stage.** The three choices give Cash 1 : 2 : 3 and cost 1.5 : 4.0 : 7.5 units, so each step up costs 1.5, then 2.5, then 3.5 per unit of time: strictly rising. Each choice is then the best one for some player: one who values 1% of loop time at under 1.5% of Shares skips; 1.5-2.5 picks Small; 2.5-3.5 Medium; above 3.5 Large. The stage multiplies all three by the same `u`, so this holds at every stage, and the price per hour saved is the same everywhere: no stage is a bargain. *Test (whole bp):* at every stage `0 < S < M - S < L - M` (LONG Seed 3 < 5 < 7; today's Series A 46 < 76 < 108).

**Shares in whole basis points.** `D = min(DilutionCap, Σ bp)`, a whole number. `base` = today's `IpoConfig.sharesFor(valuation, count, pass)` (IpoConfig.lua:168-172, whole Shares, pass included, unchanged). Paid = `floor(base x (10000 - D) / 10000)` in whole numbers, never `1 - D` as a float: `floor(100 x (1 - 0.34)) = 65` (`1 - 0.34` is 0.65999...), `floor(100 x 6600 / 10000) = 66`. Dilution comes after the pass: the same proportional loss, at most 1 Share of rounding apart from "before the pass"; `D = 0` returns `base` exactly, so old calls and tests are unchanged.

**The rounding case.** At IPO 1 today `base = 10`: `floor(10 x 9,700 / 10,000) = 9`, so a "3%" round costs 10%; a 3 bp LONG Seed round would cost 1 of 20 Shares. **Fix: round to the nearest Share and carry the rest.** `exact = base x (10000 - D) + dust` (dust in 1/10000 Share); paid = `floor((exact + 5000) / 10000)`; new `dust = exact - paid x 10000`, from -5000 to 4999, saved as `pokedex.dust` (player level, kept across IPOs; a bad value becomes 0 with a warning; written in the IPO transform's one save). IPO 1, base 10, D = 300: exact 97,000, paid 10, dust -3,000: the next IPO pays 0.3 Share less. Over a player's whole history the Shares paid stay within half a Share of exact: no round is free (its cost is carried) and none is overcharged. The window shows what this IPO really pays. *Alternative:* plain floor with the real loss shown ("-1 Share, 10%"): simpler, but small rounds overcharge.
- **Code:** a new `IpoConfig.dilutedShares(base, D, dust)` returns `paid, dust`. Callers: `preview` (IpoServer.lua:153-161), the IPO transform, IpoClient (:561, 564, 639, reading `CompanyStake` and `CompanyDust` attributes).
- **LONG_GAME (LG:86):** `dilutedShares(floor(20 x (1 + 0.25 x IPOs) x min(ratio, 1.5)^0.5 x pass), D, dust)`. IPO 1 after Large every round (D = 3,042): 20 becomes 14 (dust -840); with the pass 40 becomes 28 (dust -1,680).

**Once the 750-Share shop is complete** (LG:86), Shares buy nothing: dilution costs nothing, and stamps and the board reward only speed, so every player raises Large every round. Options, **owner decision:**
- **A. Accept it:** a reward for finishing the shop; Gold and Platinum (CUST 1.5) are fitted with "Large every round" for full-shop players.
- **B. The stake counts for stamps (recommend):** Gold needs a final stake ≥ 80%, Platinum ≥ 90% (**placeholders**). Speed or the better stamp, forever. No new saved field: the card already keeps `stake`.
- **C. Shares stay a score:** "Shares earned ever" breaks ties on the Collection board (CUST 1.6). Needs a new saved total.
- **D. A Shares sink after the shop:** repeatable cosmetic prestige items. Content work only.

**Interactions:** Shareholder (ShopConfig.lua:81-88): x2 is inside `base`, the same proportional loss. Perks: prices unchanged; fewer Shares only delay them (the IPO multiplier counts IPOs). Daily Shares (`grantShares`, IpoServer.lua:140-148) and pitch Shares (LONG_GAME, undiluted base) are never diluted. Stamps look at dilution only with option B; rounds save engaged hours, so T is fitted with S8's typical raise (CUST 5.6 S6).

## 4. Exploits (server check; test)

- **Always raise the maximum:** a design risk. The stage-scaled convex curve (section 3) and the cap: a raise that takes the total past 4,000 bp is refused; S8.
- **Raise, then reset.** (a) *The IPO:* round Cash spent on what an IPO keeps (employees, HR level, IpoConfig.lua:51-57). Fixed amounts, the dilution paid at that IPO (the record stays in `active` until the transform), LONG_GAME desk caps (R1, LG:108). Test: the transform pays `dilutedShares(sharesFor(...), D, dust)`; S8's "converter" (round Cash on eggs and HR first) gains < 3% in loop 2. (b) *Debug IpoReset* (IpoServer.lua:423-433, Studio only) leaves `pokedex` alone; test: a settled round stays settled. (c) *A version rollback* to pre-funding code pays undiluted Shares at an IPO there: owner-only, inside the floor; noted in PUBLISH_RULES "2d".
- **Raise on a throwaway, then IPO:** Cash never moves between accounts; hires do (poaching), and rounds make an alt's hires cheaper (LONG_GAME section 7). R2 (3 poach-ins per run) and R3 go live first. Test: an alt that raised the maximum feeds 4 hires, the 4th is refused; S8's alt-fed profile.
- **Amount from the client:** only `round` and `choice` are read. Test (mutation): an extra amount is ignored; NaN, 0, 1.5, "1", 4 and a stale `round` are refused; a double tap grants once.
- **Studio and live share the save key** (PUBLISH_RULES.md:46): a Studio raise sets `rounds[k].studio` and `pokedex.studio`; a live server applies saved dilution even with funding off. Test: a Studio-raised save on a fake live server: `Raise` refused, stake applied, no board write.
- **Debug grants:** valuation (IpoServer.lua:400-415) and `GiveCash` (EmployeeServer.lua:787-793) exist only in Studio (IpoServer.lua:456; ShopServer.lua:722-726 refuses on live). New rows "Funding: clear rounds", "Funding: open next round" via `ShopServer.addDebugAction` inside `RunService:IsStudio()`, setting `pokedex.studio`. Test: a source check that they are registered only there.

## 5. The message and the window

*Measured:* windows are 0.92 of the GUI, max 640 x 470 (ShopClient.lua:133-143, IpoClient.lua:294-301), with 34 px header and tabs under 330 px tall (ShopClient.lua:298-311, IpoClient.lua:789-799); 667 x 375 with a 36 px top bar is a 667 x 339 GUI (ROADMAP "Top-bar review"); every bottom-center lane is taken (-16, -72, -128, -184, -240; daily_test.py:3043).
- *Message:* one toast in the IPO lane (-16; IpoClient.lua:262-274), no new lane; the valuation bar's top line (`hudStage`, IpoClient.lua:197-207) reads "🌱 Seed · Raise a round ›", and a tap on the bar then opens the Funding window.
- *Where:* its own window, `OpenPanel = "Funding"` (CompanyClient). One window at a time (ShopClient.lua:713-735), so it never covers the Shop header, design-tutorial's "?" (TUTORIAL_PROPOSAL.md:62) or the tabs. Not a Shop tab (the tutorial strip, TUTORIAL_PROPOSAL.md:53); not a 5th IPO tab (about 49 px wide at 320 **(estimate)**).
- *Sizes* **(estimates):** 667 x 339: window 614 x 312; header 34, a line 20, three cards side by side about 192 x 120 (Cash, "-7% stake", "IPO: 18 Shares, was 20"), buttons 56 high (Later, Skip, "Raise $X"): 252 of 292 px. Portrait 320 x 532: 294 x 470, cards stacked, 72 high. PC: 640 x 470.
- *Picking:* tap a whole card, then one confirm naming the amount. **No slider:** none exists in the clients, a drag fights the page scroll and the thumbstick, and the server accepts 3 steps anyway. *Tests* like `TRAY_TESTS` (top bar 0 / 36 / 58): inside the window, ≥ 48 px tall.

## 6. Simulate before any build: S8

**S8 round size** (tools/economy_sim.py `--rounds`, next to CUST 5.6's `--pokedex`; marks are **placeholders**): policies none / Small / Medium / Large-every-round / best-per-stage, per profile, loops 1-10: hours per IPO, Shares, perk timing. Is Large always best? Which dilution curve makes the choice real? Hours saved vs Shares lost. Marks: no one choice best for every profile; Large-every-round saves ≤ 15% of a loop; converter and alt-fed gain < 3% in loop 2; raising the last open round never beats skipping it.
- *Can:* `--long` (`long_run`, economy_sim.py:1213-1379) has stage entry (:1346-1348), purchases that only fill the current rung (:1320-1339: a grant can't skip one), Shares with the pass (:1350-1352) and one speed perk, the only Shares sink and the only place dilution costs (:1362-1366). `--active` (`report_active`, :967) runs today's 5-stage economy (IPO in minutes): a smoke test only.
- *Needs:* a grant at stage entry; `dilutedShares` (whole bp, dust) after the pass at :1352; the bp table and `HoursShare` from the measured stage hours; a `rounds` policy and a chooser; the converter profile; Cash left at the IPO and the seed (Cash resets at :1368); an S8 table.

## 7. Build: PR 4b

Same rules as CUST 6 (claim, daily_test passes, F5 clean, Shut down all servers).
- **Valuation HUD / IpoClient:** `hudStage` and the bar's tap (IpoClient.lua:186-254), the Shares previews with `dilutedShares` (:561, 564, 639), IpoServer's `preview`.
- **PR 4b content:** `CompanyConfig.Funding` (`StudioOnly` on), `"Raise"`/`"SkipRound"`, `raiseRound`, the message, the Funding window, `dilutedShares` and `pokedex.dust`, the card's `rounds`/`stake`/`shares`, Debug rows. *Tests:* sections 2-5, phone sizes; `dilutedShares(base, 0, 0)` equals `base`; the bp table test (section 3). **Live only after** S8, LONG_GAME PR 2 and PR 3 (R2, R3).

## 8. Impact on other docs

- **docs/LONG_GAME_PROPOSAL.md** (`LG:` = its line): **Principle (LG:5)** "Cash can only fill a rung" holds: round Cash only buys the current rung (economy_sim.py:1320). **Pacing (LG:6-18):** the 57 h fit assumes no round; S8 decides whether it uses the typical raise. **Shares and money (LG:86, 92-94):** Shares through `dilutedShares` (section 3); the base-Cash valuation never counts round Cash; the `addEarnings` list gains "(8) `CompanyServer` never calls it". **Section 7 (LG:97-108):** rounds cheapen alt feeding: R2, R3 first. **Section 8:** PR 4b needs its PR 2 and 3.
- **Tutorial step 8 "Funding"** (TUTORIAL_PROPOSAL.md:32, "open the IPO window") becomes: when the first round opens, open the Funding window; Raise, Later or Skip completes it; no reward, never forces a raise. Step 9's reset list adds rounds and dilution (a new company starts at 100%).
- **CLAUDE.md, PUBLISH_RULES:** round Cash as a gift; "2d" (section 4's rollback note).

## 9. Open questions (unresolved, most important first)

1. **Shares once the shop is complete** (section 3): A accept, B stake counts for stamps (recommend), C Shares as a board tie-break, or D a Shares sink?
2. **Round rules:** 3 fixed choices, open rounds kept until IPO-ready, Skip final (recommend), or rounds that expire at the next stage? Numbers stay S8's.

## What I did not verify

- S8 was not run; every round number is a placeholder. The Funding window sizes and Roblox's real top bar height are not measured.
- TUTORIAL_PROPOSAL.md lives on another branch (read with `git show` for CUST); LONG_GAME PR 2 doesn't exist; `daily_test.py` was not run (docs only).
