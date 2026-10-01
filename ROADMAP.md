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
- BUILT, REVIEW FIXES APPLIED, NOT YET PLAYTESTED: M5 (2026-10-01). Review (docs/reviews/M5_REVIEW.md): F1 (card now finds the valuation bar in IpoGui, fits narrow screens) and F3 (free egg also gives the 15-minute poach protection) fixed; F2 and the other Lows listed in M9. Still needs Studio paste of OnboardingClient + OnboardingServer. Original notes: on branch milestone-5-onboarding (pushed, no PR yet). Code only: nothing synced to Studio or Roblox. New OnboardingServer (registered in the F9 load gate), OnboardingClient, OnboardingConfig and an optional `onboarding` save section. A brand-new player (no progress at all) gets one free Garage Egg, incubating on spawn, given only by the server. They tap the normal Hatch prompt (no auto-hatch exception). A glowing arrow goes pad, then egg, then pad, and ends after 1 employee + 2 upgrades. A goal tracker under the valuation bar ("Hire 3 employees", "Reach Seed stage") stays until both are done, with an X that is saved. Old saves with progress count as onboarded: no egg, arrow or tracker. No reward, no economy or IPO numbers changed, `EggsEnabled` untouched. Studio Debug: "Restart tutorial", "Act like an old save". Waiting on Mattia's playtest (new player, rejoin mid-tutorial, old save, phone size), then the PR.
- Next steps: M5 playtest + PR, then M6 (daily rewards).

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
- 7-day login calendar. Bigger reward each day, day 7 = a rare egg. Missing a day resets the streak, but show it clearly.
- "While you were away" screen with offline earnings, plus a 2x offline earnings developer product.
- Done when: rewards save, can't be claimed twice, and timezone or clock changes can't exploit them.

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
  2. Type-check `saved.cash`/`saved.owned` inside the load `pcall` instead of kicking the player on a bad value.
  3. A new field inside an existing saved section (not a new top-level section) is still deleted by older code after a rollback; carry over unknown keys per-section, or add a CLAUDE.md rule.
  4. Kept unknown sections are frozen as of join and go stale; re-check them against `team`/`ipo` on load.
  5. If `serialize` or the IPO transform errors mid-save, `data.saving` can stay true forever, blocking all later saves; build the payload inside the `pcall` and always clear `data.saving`.
- From the M5 review (docs/reviews/M5_REVIEW.md), Low findings not fixed:
  - F2: the goal card overlaps the Negotiation / Poach Alert panels on landscape phones; hide it while a poach panel shows.
  - F4: with `OnboardingConfig.Enabled = false` the saved section is `seenIntro = false, legacy = false`; treat `not seenIntro and hasProgress(data)` as legacy.
  - F5: closing the tracker during an IPO save isn't saved; retry the dismiss and say "Your IPO is being filed".
  - F6: the tracker vanishes if the only employee is lost early; save a `trackerShown` flag.
  - F7: the free-egg toast is sent during loading; send it after `data.ready`.
  - F8: server hop before the first save can re-give the egg (needs the session lock above).
  - F9: warn on bad values in the onboarding section.
  - F10: the "All goals done!" card ignores open windows for 3 s.
- F6: poach refund after a crash.
- F8: IPO balance retune.
- Before launch: sync ALL scripts to Studio and verify checksums (ShopConfig Luck Boost text was still stale in Studio on 2026-10-01 because the Studio write was permission-blocked).

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
