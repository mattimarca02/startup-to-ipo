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
