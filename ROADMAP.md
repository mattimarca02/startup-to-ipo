# ROADMAP: Startup to IPO

## Goal
About $5,000/month in DevEx payouts. That needs about $19,000/month of player spending, roughly 1,000–2,500 players online. Plan: live by week 7, then one update every week, review at day 90.

## Status (update at the end of every milestone)
- DONE M1: garage, pads, cash, saving
- DONE Shop: passes 2x Cash 199, VIP 249, Extra Employee Slots 149, Auto-Hatch 199, Headhunter 149. Products: Pile/Bag/Vault of Cash 29/99/299, Luck Boost 49, Instant Hatch 25, Poach Shield 49. All exist on Roblox.
- DONE M2: recruiting eggs, creature employees. ShopConfig.EggsEnabled = false and the 4 egg items are off sale until launch.
- DONE M3: poaching (merged). PR #2 poaching-cleanup merged: 2-player poach, counter-offer and the leave/refund case all passed manual testing.
- IN REVIEW M4: IPO rebirth built on milestone-4-ipo (PR open): valuation, 5 funding stages, Go Public with two-step confirm, x multiplier + Shares, IPO shop (6 perks), gold IPO pad, in-server leaderboard, Debug tools. Merge after Mattia's playtest. The early start on claude/task-1iff57 was reviewed and replaced (its IpoConfig was rewritten); that branch is no longer needed.
- NOT SYNCED: game pass "Shareholder" (2x Shares, R$ 199) is in ShopConfig with id = 0 and shows "Coming soon". Run sync_monetization on the PC to create it on Roblox.
- Tooling: GitHub repo, sync_monetization (PC only, API key in .env.txt), Studio MCP on PC and MAC.

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
- DataStore session locking (prevent the two-server edge case), request budgets, retry logic.
- Full exploit review of every RemoteEvent. Mobile pass on every screen.
- Analytics: onboarding funnel, economy events and purchase events via AnalyticsService.
- Reset all dev saves, set EggsEnabled = true, run sync_monetization (PC), final 2-client test, then publish.

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
