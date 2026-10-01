# M6 plan: daily rewards and return loop

Planning only. No game code, no Studio, no Roblox changes in this doc or on this branch (`milestone-6-daily-rewards`).
Goal from ROADMAP.md: *"rewards save, can't be claimed twice, and timezone or clock changes can't exploit them."* Play days per user and day 1/7/28 retention are what this milestone is for.

Sources read: CLAUDE.md, ROADMAP.md (M6), docs/ECONOMY.md, docs/M5_PLAN.md, docs/reviews/M5_REVIEW.md, plus `TycoonCore.lua`, `IpoConfig.lua`, `IpoServer.lua`, `EmployeeServer.lua` and `OnboardingServer.lua` for the facts below.

## 1. The daily reward loop

**What the player sees.**

- Once per join, when a reward is waiting, a **Daily Reward window** opens by itself. It shows a 7-day calendar (4 cards on top, 3 below on a phone), today's card highlighted, finished days ticked, and one big **Claim** button.
- If they close it, a small gift chip with a dot stays on the screen until they claim (UI details in section 6). After claiming, the chip shows "Next reward in 5h 12m" (a countdown to the next reset).
- The window never opens by itself for a player who is still in the M5 first minute (see section 6), and never while another window is open.

**The calendar** (all numbers live in a new `DailyConfig`; this is the first proposal, tested in section 2):

| Day | Reward | Built from |
|---|---|---|
| 1 | Cash: 5 min of your income | Cash |
| 2 | Cash: 10 min of your income | Cash |
| 3 | 1 Garage Egg | existing egg, `EmployeeServer.grantEgg` |
| 4 | Cash: 20 min of your income | Cash |
| 5 | 1 Startup Egg | existing egg |
| 6 | Cash: 30 min of your income | Cash |
| 7 | 1 **Unicorn Egg** (the "rare egg" from ROADMAP: 8% Legendary) + 3 Shares | existing egg, Shares |

- **Cash is "minutes of income", not a fixed number.** The server multiplies the minutes by the player's current Income at the moment of the claim. A day-1 player gets a few hundred, a player after three IPOs gets millions, so the reward stays meaningful and never breaks the early game.
- **Eggs go straight into a free incubator**, with the normal timer, and the egg's odds are shown on the card (design rule: show odds). They are free and not random to receive. Only the hatch is random, exactly like the free M5 egg.
- **Shares** are the existing IPO currency. Only day 7 gives any, and only 3 (the cheapest perk level costs 5).
- **No new currency.** Nothing here is a Robux item (section 5).

**How the streak works.**

- Claim on consecutive days and the calendar moves forward: Day 1, 2, ... 7. After day 7 it starts again at Day 1, and the best streak is remembered for display.
- A "day" is a UTC calendar day decided by the server (section 3). One claim per day.

**What happens when a day is missed.**

- Missing one or more days sends the next claim back to **Day 1**. This is what ROADMAP says, and the UI makes it clear instead of silent: the window says "You missed 2 days. Your streak was Day 4. Today is Day 1." in a calm, neutral tone, with no red, no pressure and no countdown on the lost streak.
- A missed day costs nothing else. Nothing the player owns is touched, and no Robux "restore streak" exists (section 5).
- A Day 3, 5 or 7 egg needs a free incubator. If all are busy the claim is refused with "Free an incubator first", and **the day is not used up**; the player can finish or hatch an egg and claim again before the day ends. It's a rare case, because the base game has 3 incubators and Garage eggs hatch in 60 s. Listed as a risk in section 7.

## 2. Economy fit

**Question:** do the rewards move the IPO timing we just tuned (first IPO about 12 min of active play, a 2-hour binge capped near IPO 5, see ECONOMY.md section 3)?

**Method.** I ran the real `tools/economy_sim.py` unchanged, with one extra step at the first login of each simulated day that applies the calendar above (a throwaway copy outside the repo; build step 4 adds this hook to the real script and a `DAILY_*` block to its CONFIG). Every simulated player claims every day, which is the **worst case** for distortion. 30 days, IPO on, no passes, no perks, median of 30 runs. Cash from the calendar is treated as a **gift**: it is added to the player's Cash but not to their valuation (like refunds today; see "Cash rule" below).

| Behaviour | Calendar | 1st IPO, minutes online | IPOs by day 7 | IPOs by day 30 | Shares at day 30 |
|---|---|---|---|---|---|
| active (3x20 min/day) | none (today) | 11.7 | 10 | 12 | 179 |
| | **proposed** | **11.7** | **10** | **12** | **192 (+7%)** |
| | proposed, but Cash counts as valuation | 8.7 (-25%) | 10 | 12 | 179 |
| | too generous (Startup d3/d5, Unicorn d7 + 10 Shares) | 11.7 | 10 | 12 | 220 (+23%) |
| casual (1x10 min/day) | none | 10.0 (first IPO at day 2) | 7 | 10 | 229 |
| | **proposed** | **10.0** | **7** | **10** | **246 (+7%)** |
| | proposed, but Cash counts as valuation | 8.7 (-13%) | 7 | 10 | 211 |
| idler (1 min/day) | none | 2.0 (first IPO at hour 48) | 6 | 10 | 210 |
| | **proposed** | **1.0 (first IPO at hour 24)** | **6** | **10** | **174** |

**What the table says:**

- **The first IPO does not move** for the active and casual players: 11.7 and 10.0 minutes with the proposed calendar, same as today, and the IPO counts at day 7 and day 30 do not change either. The 2-hour binge is a single day, so it only ever gets the Day 1 reward (about 300 Cash at minute 0), which is below the noise.
- **Cash is a gift and must stay out of the valuation.** If the calendar's Cash counted like income (the way offline earnings and Cash packs do), the first IPO would come 25% sooner for the first-day player (8.7 min), and later rewards (30 minutes of income) would add real valuation to every run. So: **calendar Cash goes to `cash.Value` only, never through `addEarnings`.**
- **Shares are the one lever.** The proposed 3 Shares a week adds about 7% to Shares over 30 days (13 Shares for the active player, 17 for the casual). Ten Shares a week would add 23%, which makes the IPO shop (525 Shares in total) noticeably cheaper. Stay at 3 or lower.
- **The idler's first IPO moves from hour 48 to hour 24.** It is a real effect: Day 1 Cash lets a 1-minute player buy the egg at the login that would otherwise have been too short. It helps exactly the player this milestone targets (day-1 return), and it doesn't change the ECONOMY.md "idler" floor after that.
- **The idler's Shares fall (210 to 174).** This is a quirk of the simulator, not of the rewards: it takes the IPO the moment it is available, so an earlier first IPO means 10 Shares instead of a bigger offline-overshoot payout (the weakness already noted in ECONOMY.md section 3b). Don't read it as a loss of 36 Shares.
- **Cash alone is not a retention driver for veterans.** ECONOMY.md findings 3 and 4 say Cash has nothing to buy after the first hour; a Unicorn egg costs 36 seconds of income. So the Cash days matter in a new player's first week, which is where day 1/7 retention is decided, and the eggs and Shares days are what a veteran actually wants. That is why Cash is proportional to income and why days 3, 5 and 7 are eggs.

**Cash rule (one line for the code).** Calendar Cash is added to `data.cash` only. It is never passed to `core.addEarnings`, so it can't raise the valuation, change the IPO stage or change the Shares an IPO pays.

**Values in config.** Everything above lives in a new `DailyConfig` (ReplicatedStorage), nothing in logic:

```lua
DailyConfig.Enabled = true
DailyConfig.Days = {   -- the calendar; a cycle is #Days long. Never reuse or rename a day's "key" after shipping.
  { key = "Day1", cashMinutes = 5 },
  { key = "Day2", cashMinutes = 10 },
  { key = "Day3", egg = "Garage" },
  { key = "Day4", cashMinutes = 20 },
  { key = "Day5", egg = "Startup" },
  { key = "Day6", cashMinutes = 30 },
  { key = "Day7", egg = "Unicorn", shares = 3 },
}
DailyConfig.CashMaxMinutes = 60       -- hard cap on any cashMinutes, so a bad config can't print money
DailyConfig.ResetHourUtc = 0          -- the day changes at this UTC hour (see section 3)
DailyConfig.ClaimDebounce = 1         -- seconds between two Claim requests from one player
```

A config check at the bottom (like `IpoConfig`) warns about a missing egg key, a reward with nothing in it, or `shares` above a sensible limit.
