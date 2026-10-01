# ROADMAP: Startup to IPO

## Goal
About $5,000/month in DevEx payouts. That needs about $19,000/month of player spending, roughly 1,000–2,500 players online. Plan: live by week 7, then one update every week, review at day 90.

## Status (update at the end of every milestone)
- DONE M1: garage, pads, cash, saving
- DONE Shop: passes 2x Cash 199, VIP 249, Extra Employee Slots 149, Auto-Hatch 199, Headhunter 149. Products: Pile/Bag/Vault of Cash 29/99/299, Luck Boost 49, Instant Hatch 25, Poach Shield 49. All exist on Roblox.
- DONE M2: recruiting eggs, creature employees. ShopConfig.EggsEnabled = false and the 4 egg items are off sale until launch.
- DONE M3: poaching (merged). PR #2 poaching-cleanup merged: 2-player poach, counter-offer and the leave/refund case all passed manual testing.
- DONE M4 (2026-10-01): IPO rebirth merged (PR #6, branch milestone-4-ipo): valuation, 5 funding stages, Go Public with two-step confirm, x multiplier + Shares, IPO shop (6 perks), gold IPO pad, in-server leaderboard, Debug tools. Mattia's playtest passed: eggs, HR, IPO, perks, poach UI and IPO screen at phone size, and the rejoin test. The early start on claude/task-1iff57 was reviewed and replaced (its IpoConfig was rewritten); that branch is no longer needed. Publish needs **Shut down all servers** (new save section, see F2 in docs/reviews/M4_REVIEW.md).
- The game now belongs to the Roblox group (universe 10768772528, place 86395856666175, same IDs as before). The sandbox copy is archived.
- DONE: Shareholder game pass (2x Shares per IPO, 199 R$, ID 2001728902) created with sync_monetization and merged (PR #10). Studio test passed: +20 Shares with the pass ON vs +10 OFF at IPO #2. The IPO retune is merged too (PR #9).
- Tooling: GitHub repo, sync_monetization (PC only, API key in .env.txt), Studio MCP on PC and MAC.
- DONE: Luck Boost wording fixed (ShopConfig.lua:117 shows "Legendary chance 8.0% -> 9.7% (Unicorn Egg)", not "2x").
- DONE: IPO retune (branch ipo-retune). economy_sim.py reads the real IpoConfig.lua values; Stages and StageGrowthPerIpo retuned (Seed 1800, growth x2.5) so the first IPO lands at ~10-15 min of active play. See docs/ECONOMY.md section 3.
- DONE (PR open, not merged, branch fix-security-review): 3 security-review fixes. (1) Going public calls off poach deals against you and refunds the poacher, and drops your Counter-Offer, instead of refusing the IPO. (2) No employee duplication: addEmployee refuses a duplicate ID and clears `outgoing`, saves with duplicate IDs load clean, no poaching with a save that didn't load. (3) A failed save load is retried 3 times, then the player is kicked (no silent unsaved session). Needs the 2-client Mac tests in the PR before merging.
- DONE M5 (2026-10-01): onboarding merged (PR #15, branch milestone-5-onboarding). Review (docs/reviews/M5_REVIEW.md) found no Critical or High issues; F1 (goal card finds the valuation bar, fits narrow screens) and F3 (free egg also gives the 15-minute poach protection) fixed; the other Lows are in M9. Studio playtest passed: new player, poach shield, old save, rejoin mid-tutorial. New players get one free Garage Egg, a glowing arrow and a goal tracker; old saves count as onboarded. New optional `onboarding` save section. Publishing M5 needs **Shut down all servers** (new save section).
- DONE M6 (2026-10-01, merged as PR #17, branch milestone-6-daily-rewards): 7-day login calendar. One claim per UTC day, decided by the server; one missed day keeps your place, 2+ go back to Day 1 (said calmly in the window). Rewards: Cash days (5/10/20/30 min of income, min $300, a gift that never counts toward the IPO valuation), Garage Egg (d3), Startup Egg (d5), Unicorn Egg + 3 Shares (d7, Shares not doubled by Shareholder; no egg is sold for Robux, so the Unicorn Egg stays). Gift chip right of the valuation bar (the bar leaves room on narrow screens), Daily window, IPO confirm reminder, Studio Debug (fake next day, reset). New optional `daily` save section in the all-modules-loaded gate. Logic tests: tools/daily_test.py (69 checks). Sim: tools/economy_sim.py --daily (first IPO unchanged, Shares +7-8%). Review (docs/reviews/M6_REVIEW.md): 0 Critical/High/Medium, 8 Low; F1, F3, F6, F8 fixed, F2/F4/F5/F7 in the M9 list; daily_test.py 69/69. Studio playtest passed (new player, claim, double claim, rejoin, missed days, full incubators, day 7 Shares, IPO keeps the streak, malformed calls) and the phone layout and claim tap were checked by hand. Publishing M6 needs **Shut down all servers** (new save section). CLAUDE.md lists the M6 additions (F8).
- **Before publishing M6:** use **Shut down all servers** (new `daily` save section), and decide `ResetHourUtc` in DailyConfig before launch (review finding F3).
- Open PRs: #13 (Shares per IPO grow with the IPO count) and #14 (security review fixes) are still open with docs-only conflicts (CONTRIBUTING/ROADMAP). `tools/economy_sim.py` must be re-run after #13 merges because it changes the Shares figures.
- Next steps: sort out #13 and #14, then M7 weekly events.

## Milestones, in order

### M4: IPO rebirth
Long-term goal and retention driver.
- Funding stages shown in the UI: Garage, Seed, Series A, Series B, IPO. Each stage needs a higher company valuation (total earned).
- IPO resets cash and garage buildings/upgrades. Keeps employees, passes, owned products and HR level.
- Each IPO gives a permanent income multiplier and Shares, a new currency for an IPO shop (permanent perks: faster egg timers, +1 incubator, offline income cap up, better base luck).
- Valuation and IPO count are visible to others (leaderboard), so it acts as a status symbol.
- Done when: IPO works end to end, saves, old saves load, Debug can grant valuation.

### M5: First minute (onboarding)
First-play bounce rate is Roblox's #2 discovery signal.
- No text tutorial. A new player gets a free Garage Egg on spawn, a glowing arrow to the first pad, and a first employee within 60 seconds.
- Short goal tracker ("Hire 3 employees", "Reach Seed stage") for the first 10 minutes.
- Done when: a new player earns, hatches and buys within 60 seconds without reading anything.

### M6: Daily rewards and return loop
Play days per user and day 1/7/28 retention drive recommendations.
- 7-day login calendar. Bigger reward each day, day 7 = a rare egg. Missing one day keeps your place; missing 2 or more resets to Day 1, shown clearly and calmly.
- A new day is the UTC calendar day, decided by the server, with a countdown to the next claim.
- Done when: rewards save, can't be claimed twice, and timezone or clock changes can't exploit them.

### M6b: While you were away
Split out of M6 (Mattia's answer to the M6 plan, open question 2).
- "While you were away" screen with offline earnings (TycoonCore tells the client the offline amount; display only).
- 2x offline earnings developer product: new product in ShopConfig with `id = 0` (owner runs sync_monetization), granted only in ProcessReceipt, plus a rule for doubling an amount that was already paid at load.
- Done when: the screen shows the real offline amount, and the product doubles it once, idempotently.

### M7: Weekly events system
Top games update on a fixed weekday with timed events.
- Config-driven limited-time egg with an exclusive creature, rotated weekly from config without code changes.
- Server-wide timed event ("Market Boom": 2x income for 15 min) on a fixed schedule with a countdown, plus a manual trigger for live sessions.
- Done when: next week's event can be set up by editing config only.

### M8: Store page
Play-through rate is Roblox's #1 discovery signal.
- Icon, 3+ thumbnails, title and description that explain the game instantly (hatch employees, steal rivals' staff, IPO).
- Done when: assets uploaded and a few variants ready for Roblox's thumbnail testing.

### M9: Pre-launch hardening
- DataStore session locking (prevent the two-server edge case), request budgets, retry logic. (F10)
- Full exploit review of every RemoteEvent. Mobile pass on every screen.
- Analytics: onboarding funnel, economy events and purchase events via AnalyticsService.
- Reset all dev saves, set EggsEnabled = true, run sync_monetization (PC), final 2-client test, then publish.
- From the M4 re-review (docs/reviews/M4_REREVIEW.md), 5 Low findings:
  1. If the pass check times out, loading continues without passes; pay the missing offline difference when it answers, and refuse `GoPublic` until it answers.
  2. Type-check `saved.cash`/`saved.owned` inside the load `pcall` instead of kicking the player on a bad value. (Done in PR #14 F1, c564c96.)
  3. A new field inside an existing saved section (not a new top-level section) is still deleted by older code after a rollback; carry over unknown keys per-section, or add a CLAUDE.md rule.
  4. Kept unknown sections are frozen as of join and go stale; re-check them against `team`/`ipo` on load.
  5. If `serialize` or the IPO transform errors mid-save, `data.saving` can stay true forever, blocking all later saves; build the payload inside the `pcall` and always clear `data.saving`.
- From the PR #14 re-review (docs/reviews/PR14_REREVIEW.md), Low findings not fixed:
  - R3: a Studio dummy deal (`ignoreShields`) that ends during the IPO save moves the employee, then errors; check `poachOf(target) == nil` in `finish` before the `ignoreShields` branch.
  - R4: a deal cancelled during a failed IPO save says "got protected" and a comment claims it is left as it was; reword both ("X is going public").
  - R6: a `lastSeen` that is a finite number but absurdly old (0, -1) pays the full offline cap; require `lastSeen > 0` or ignore values over a year old.
  - R7: run `python tools/daily_test.py` and paste the "N passed, 0 failed" line in the PR before merging.
  - R8: `IpoServer` `number()` accepts `math.huge` (`ipo.count = inf` blocks every IPO); add `and value < math.huge`.
- From the M5 review (docs/reviews/M5_REVIEW.md), Low findings not fixed:
  - F2: the goal card overlaps the Negotiation / Poach Alert panels on landscape phones; hide it while a poach panel shows.
  - F4: with `OnboardingConfig.Enabled = false` the saved section is `seenIntro = false, legacy = false`; treat `not seenIntro and hasProgress(data)` as legacy.
  - F5: closing the tracker during an IPO save isn't saved; retry the dismiss and say "Your IPO is being filed".
  - F6: the tracker vanishes if the only employee is lost early; save a `trackerShown` flag.
  - F7: the free-egg toast is sent during loading; send it after `data.ready`.
  - F8: server hop before the first save can re-give the egg (needs the session lock above).
  - F9: warn on bad values in the onboarding section.
  - F10: the "All goals done!" card ignores open windows for 3 s.
- Phone layout check of the M5 goal card (portrait 320x568 and landscape 667x375) done by hand, and the poach shield timer display after grantFreeEgg.
- F6: poach refund after a crash.
- From M6: the daily claim's two-server gap (F10). With no session lock, a player who hops to a second server before the first server's claim save lands loads the old save there and can claim the same day again. Whichever server saves last wins, so the save normally ends with one reward and loses the other server's seconds of progress; a reward only survives twice if it left the save in between (e.g. the hatched employee was poached by someone else). Closed by the session lock above.
- From the M6 review (docs/reviews/M6_REVIEW.md), Low findings not fixed:
  - M6 F2: on Day 7, check `IpoServer.isBusy` before the egg is granted, so a Shares refusal can't consume the day with only part of the reward.
  - M6 F4: the Studio Debug "Daily: next day" and "reset" buttons are saved to the real save (note it in the row text).
  - M6 F7: the chip's poach-panel hook gives up after 30 s; wait without a timeout or listen to `PlayerGui.ChildAdded`.
- From the PR #14 review (docs/reviews/PR14_REVIEW.md), Low findings not fixed:
  - PR14 F4: if `poached()` returns false after a successful roll (the new duplicate refusal), `finish` keeps the poacher's Cash as if defended; refund `negotiation.cost` with a "deal fell through" message instead.
  - PR14 F5: the give-back after a failed move ignores `EmployeeServer.addEmployee`'s result and its capacity check; add `EmployeeServer.restoreEmployee` that re-inserts the original employee at its old index and clears `team.outgoing[id]`.
  - PR14 F7: during a DataStore outage the load retry makes 3 `GetAsync` calls per join; check `GetRequestBudgetForRequestType` before each retry (or accept it).
  - PR14 F8: the comment on `PoachServer.isBusy` says a poacher can never stop an IPO, but a finished poach holds it for up to ~60 s while it saves; say so.
- Studio playtests need **Enable Studio Access to API Services** ON (Game Settings > Security), or the 6 s load retry kicks the player. (PR14 F6, no code change.)
- Before launch: read Roblox's current policy pages on rewards (Paid Random Items, monetization, and anything on daily or login rewards) in the Creator Hub and confirm the M6 calendar still fits (no Robux in the daily window, fixed and visible rewards, odds shown for the eggs).
- F8: IPO balance retune.
- Before launch: sync ALL scripts to Studio and verify checksums.

### Launch requirements (start now, they take time)
- New games first reach age-checked players 16+ only. Under-16s unlock after 250 plays by "highly engaged" players within 60 days.
- Needs ID verification, 2-step verification, and 2+ months of Roblox Plus or a refundable fee.
- So the theme must appeal to teens and adults at launch. Startup satire fits.

### After launch (weekly)
- One update every week on the same weekday: new limited egg or creature, balance changes, one new feature.
- Cosmetics drive spending: creature skins, garage and office themes, VIP cosmetics.
- Move the game to a Roblox group before revenue starts (100 Robux) to split earnings.
- Short-form video clips of poaching and IPO moments for TikTok and YouTube.
- Paid ads only after the game already monetizes. Fix onboarding if a campaign shows no progress in 3–5 days.

## Design rules
- Original theme, names and art only. No copying Steal a Brainrot, Grow a Garden or similar (their owners sue imitators).
- Show odds for every egg and boost.
- Poaching must never feel crushing: keep the victim protections.
- Server authority, config-driven items, old saves must always load (see CLAUDE.md).

## How each milestone is built
1. New branch per milestone, named milestone-N-name.
2. Build, playtest via Studio MCP as far as possible, list the tests Mattia must do by hand.
3. Open a PR. Merge only after Mattia confirms the playtest.
4. Update the Status section above.
5. Report format: files changed, test results table, manual steps, what to click in Studio (Save to Roblox / Publish).
