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
| | proposed, but Cash counts as valuation | 8.7 (day 1, not day 2) | 7 | 10 | 211 |
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

## 3. Time and exploits

**Time source.** The server's `os.time()` (UTC seconds). It is the same clock the game already trusts for `lastSeen`, egg `hatchAt`, shield timers and the IPO cooldown, so there is no new kind of trust. The day number is:

```lua
dayNumber = math.floor((os.time() - DailyConfig.ResetHourUtc * 3600) / 86400)
```

- **UTC calendar days.** The day changes for every player at the same moment (UTC midnight by default), and a "Next reward in 5h 12m" countdown is the same on every phone. The cost: for players far from UTC the reset lands at an odd local hour, and someone can claim at 23:59 and again at 00:01 UTC. That doesn't cheat the calendar (still one claim per day, 7 claims need 7 different days), it only means two claims can be 2 minutes apart.
- The alternative, a rolling 24 hours from the last claim, drifts later each day and needs a second "grace" rule. I don't recommend it; it is open question 3 if you want it.
- The countdown on the client uses `workspace:GetServerTimeNow()` plus a server-sent reset time. Display only: the client's own clock is never used for anything.

**What the server stores and decides.** Only `lastClaimDay` (a day number) and `streak`. At claim time the server computes `diff = today - lastClaimDay` itself:

| diff | Meaning | Result |
|---|---|---|
| 0 | already claimed today | refused, nothing changes |
| 1 | consecutive | `streak + 1`; reward is calendar day `(streak % #Days) + 1` |
| 2 or more, or no section | missed days, or a new player | streak restarts at 1: reward is Day 1 |
| negative, or far in the future | bad data or the server clock went back | treated as "claimed today", warning in the log, **never** grants and never locks the player out for good (a value more than 1 day ahead is clamped to today) |

**What stops each trick:**

| Attack | Why it fails |
|---|---|
| **Changing the device clock or timezone** | The client sends no time, day or streak. The only request is `Claim` (a string), and the server works everything out from its own `os.time()` and the saved `lastClaimDay`. The countdown is cosmetic. |
| **Double claim (spamming the button, two quick requests)** | The handler has no yield between "check `diff >= 1`" and "set `lastClaimDay = today` and apply the reward", so the second request already sees today's marker and is refused. A per-player debounce (`ClaimDebounce`, 1 s) and `data.ready` add to that. The remote ignores extra arguments. |
| **Reward without the marker (or marker without the reward)** | They are written in the same in-memory step and land in the same `save()` payload (the same argument as the M5 free egg, review section 2). They can't be saved apart. If the save fails, neither is stored and the player can claim again next join: nothing was lost or doubled, because the reward is lost with the marker. |
| **Rejoin spam** | Joining grants nothing: a reward is only given by a `Claim` request, never by `PlayerAdded`. Rejoining just shows the same "claimed" or "ready" state read from the save. An immediate save after each claim (like `ProcessReceipt`) keeps the window short. |
| **Two servers at once (M4 F10, M5 F8)** | The honest answer: there is **no session lock yet** (planned for M9), so M6 can't fully close this. What M6 does: Roblox lets one account be in one server at a time, so the exploit is a hop in the seconds a save is in flight. The claim saves immediately and tells the client "Claimed" only after the save answers. The worst case left is one extra reward (a few minutes of Cash, one egg) for a hop timed to the second, and the second server's later save overwrites the first, so the player ends with one copy anyway. M9's session lock closes it for good. This must be recorded in the M6 review, not hidden. |
| **Hostile or corrupted save** | `daily` fields are type-checked on load: numbers must be finite and non-negative whole numbers, otherwise they are skipped with a `warn` (never an error). Unknown fields inside the section are kept and written back. |
| **Client asks for a different day or a bigger reward** | No remote carries a day, an amount or a reward key. The reward is looked up in `DailyConfig` from the server's own streak, and Cash is capped by `CashMaxMinutes`. |
| **Claiming during an IPO save** | `data.ready` is false while the IPO is saved, so the claim is refused with "Your IPO is being filed, try again in a moment" (the M5 F5 lesson: say why, and let the button retry). |
| **Egg days with no free incubator** | Refused before anything is changed, so no marker is written and the day is not consumed. |

**Never trusted from the client:** a time, a date, a streak, a day number, a reward amount, or "I claimed already". The only message a client sends is `Claim`.

## 4. Save

A new optional top-level section, written by `DailyServer.serialize` through TycoonCore's `save()` like every other module (no second DataStore, no second save loop):

```lua
daily = {                       -- DailyServer.serialize (optional: older saves have none)
  lastClaimDay = number,        -- day number (see section 3) of the last claim; 0 = never claimed
  streak = number,              -- consecutive days claimed (0 = none yet); the next reward is day (streak % #Days) + 1
  best = number,                -- longest streak ever (display only)
  claims = number,              -- total claims (display and analytics only)
}
```

**Rules from CLAUDE.md, and how this follows them:**

- **Optional with defaults (F2 behaviour).** A save with no `daily` section (every save today) loads as `lastClaimDay = 0, streak = 0, best = 0, claims = 0`: the player can claim Day 1 on their first join after M6. Bad values are skipped with a `warn`, never an error. Unknown fields inside the section are kept and written back, the same way `OnboardingServer` does (`KNOWN_FIELDS`, M4 re-review finding 3).
- **TycoonCore changes** (all small, the same pattern as `onboarding`): add `daily = true` to `KNOWN_SECTIONS` so older code can't wipe it and this code keeps newer ones; add `data.daily` to the "a save must have every part" check in `save()`; add `daily = DailyServer.serialize(data)` to the payload; call `DailyServer.setupPlayer(player, data, saved and saved.daily)`.
- **Joins the "all modules loaded" gate (M4 F9).** `DailyServer.setupPlayer` runs inside the same setup `pcall`, after `OnboardingServer.setupPlayer` and before `data.loaded = ok`. It does no DataStore call and nothing that yields, so it can't delay the gate. If it errors, the player is kicked and nothing is saved, so a half-loaded `daily` can never overwrite a good one. `save()` also refuses while `data.daily` is missing.
- **Section order matters for one thing only:** `DailyServer` must run after `EmployeeServer.setupPlayer`, because a claim calls `EmployeeServer.grantEgg`. Setup itself grants nothing.
- **Nothing is changed at load.** The "missed a day" case is computed from `lastClaimDay` when the player asks for the state, so loading and rejoining never change the save. Only a successful claim writes to it.
- **Old code after a rollback** keeps the section (it is in `KNOWN_SECTIONS` only for M6 code, but M4+ code already writes back unknown sections). Code from before the M4 F2 fix would drop it, which is why the publish needs **Shut down all servers**, as for M4 and M5.

**What an IPO does to the streak: it keeps it.** Checked in the code:

- `IpoConfig.Resets` lists only Cash, Upgrades, Eggs and HRDepartment.
- `commitIpo`'s transform in `TycoonCore.lua` changes only `payload.cash`, `payload.owned`, `payload.team.incubators`, `payload.poach.hrLevel` and `payload.ipo`. It never touches `payload.daily`.

So the streak, `lastClaimDay` and `best` survive an IPO with no code change, and no entry is needed in `IpoConfig.Resets` (the streak is real time, like shields and cooldowns, not part of the run). What an IPO does change:

- **Cash rewards scale up** after an IPO, because the multiplier raises Income.
- **A claim made before an IPO** puts the Cash on the run that is about to be reset, and a Day 3/5/7 egg in an incubator is cleared by the IPO (`Resets.Eggs = true`). The Daily window warns once: "Tip: claim after your IPO" is **not** needed for fairness (no exploit: the reward is gone, nothing is gained), but it is a polite line on the IPO confirmation. Open for the UI step, not a rule.
- **Claim during the IPO save** is refused (section 3) so nothing is granted into a state that is about to be replaced.

## 5. Roblox rules and monetization

The rules that apply, from CLAUDE.md and ROADMAP.md (CLAUDE.md has the purchase rules; the under-16 rules are in ROADMAP's Launch requirements, not in CLAUDE.md):

| Rule | How M6 follows it |
|---|---|
| Nothing is sold for the daily reward | There is **no Robux button, product or pass in the daily window**: no "restore my streak", no "2x today's reward", no "skip the wait". Every player gets the same calendar for free. |
| Paid random rewards (loot-box style) need odds shown, and the design rule is "show odds for every egg and boost" | The reward is **fixed and known in advance** (the whole calendar is visible), and nothing is bought with Robux. The eggs on days 3, 5 and 7 are free and their hatch is random, so each egg card shows its odds from the same `CreatureConfig.getOdds` the egg panel uses. |
| Not tied to a pass in a way that breaks the rules | No pass changes whether, when or what you can claim. One honest side effect: Cash days are minutes of **your current Income**, and a 2x Cash pass already doubles Income, so pass owners see a bigger Cash number. It is the same proportional rule as offline earnings, it is not a paid reward, and the card says "10 min of your income" so it isn't hidden. If you'd rather not have it, the server can compute from Income without passes (open for review, not a question). |
| Developer products only in `ProcessReceipt` | M6 adds no purchase. (The "2x offline earnings" product from the ROADMAP is a separate piece, see open question 2; if built, it follows the `ProcessReceipt` rules.) |
| Never trust the client | Section 3. The client sends only `Claim`. |
| Under 16 / chat safety | New games first reach 16+ players only (ROADMAP Launch requirements). The daily window has **no free-text input**: only taps (Claim, Close). Nothing links to chat, trading or other players. |
| Pressure and wording | The window uses a calm tone and no fake urgency: no flashing red countdown, no "you will lose everything" text, no "come back or else". A lost streak is stated as a fact ("Your streak was Day 4. Today is Day 1."). This matters more as soon as under-16s unlock. |

**What I could not check from here:** the current Roblox policy pages on rewards and monetization. The above applies the rules in the repo. Before launch, someone should read Roblox's current "Paid Random Items" and monetization policies in the Creator Hub and confirm. Nothing in this plan depends on a gray area, because nothing is sold.
