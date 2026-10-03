# Active loops: one task engine (proposal, design only)

Branch `active-loops`; no game code changed. Numbers are **starting values**, mirrored in `tools/economy_sim.py` (`ACTIVE_*`; per-rung budget and unlock map in the `--long` block; `python tools/economy_sim.py --active --runs 40 --days 365` and `--long`). Pacing, Shares, the away rule and the PR order live in `docs/LONG_GAME_PROPOSAL.md`, which **supersedes** this doc's old IPO-timing and Shares-shop parts. `IpoConfig`, perks and the pass multiplier are untouched here.

## 1. The engine

`TaskServer` runs every task from one `TaskConfig` row. It is a feature module like `DailyServer` (`init(core)`, `setupPlayer`, `serialize`), plugged in by TycoonCore in the all-modules-loaded gate, after `EmployeeServer` and `IpoServer` and **before `DailyServer`** (which stays last). **In PR 1 tasks run only in Studio** (`TaskConfig.Enabled` and `RunService:IsStudio()`, like `DebugInStudio`): `addEarnings(kind)` arrives only in PR 2, so no live player earns task Cash before the economy core. `TaskClient` draws; remotes `TaskRemotes` (`TaskAction`: `Answer`, `Choose`, `Hit`, `Skip`, `Start`; `TaskState` server to client).

```lua
Call = { wave = 1, role = "sales", action = "click",         -- click | choose | timing | targets
  every = {20, 40}, queue = 3, limit = 8,                    -- gap (s), max waiting, time to act (0 = waits)
  reward = { seconds = 7, chain = { step = 0.1, max = 2 } }, -- seconds of the player's current Income
  miss = 0, auto = 0.20, demand = 0.08, cooldown = 0, unlock = { rung = 0 } }
```

**Actions.** The server owns answer, clock and reward; the client sends only `{taskId, answer}`: **click** (tap before `limit`), **choose** (2-3 options, server grades), **timing** (the press must land in a server window plus ping, max 0.3 s), **targets** (server places them, client sends an index).

**Arrival and demand.** Gap = `U(every) / (D x R)`; **`D = min(2.0, 1 + demand x hires)`** (demand 0.04-0.08; the cap is `ACTIVE_DEMAND_CAP` in the sim and binds from 13 hires for the 0.08 rows), `R = min(1.4, 1 + 0.02 x level)`.

**Employee auto-resolve.** Roles from `CreatureConfig` (sales, eng, ops, mkt, fin). The team takes an arrival with `A = min(0.75, 1 - (1 - auto)^n_role)`; the founder keeps at least 25%. A team-taken task pays 50% (no chain), only while the player is present, shown as one "Team handled 4 calls" line. Only **routine** tasks (calls, bugs, tickets, pickups, shipping) can be taken; **exceptions** (pitch, events, negotiation, crisis, launch, roadshow) never.

**Caps and skip.** `queue` per row (a full queue drops the arrival), at most 3 chips on screen. **Skip** is free and keeps the chain; only an expired call breaks it. **Quiet mode:** after 3 expiries in a row or 90 s without a graded answer, no new tasks until the player acts. **Difficulty:** `level = rung + min(IPOs, 10)`: gaps up to x1.4 faster, limits `x max(0.65, 1 - 0.03 x level)`, odds -0.8% per level. A task appears at its rung (table below), after the first IPO all are on; tiers 2 and 3 appear one and two rungs later. **Stage to rung in PR 1** (5 stages until PR 2 adds `SeriesCD` and `PreIpo`): Garage 0, Seed 1, Series A 2, Series B 3, IPO-ready 4 (Series C+D budget and difficulty).

**Rewards.** Cash = `seconds x data.income.Value` (passes and IPO multiplier included) through `addEarnings(kind = "task")` (PR 2; in PR 1 the Studio-only tasks use the existing wrapper), valued at base Cash (LONG doc section 6). Boosts: one per source, total cap +50%, not saved. **Reward budget** (autoclicker wall): per online second at most `B(rung)` seconds of Income, bank 60 s, beyond it 20% (section 4). No pay during `IpoServer.isBusy` or before `data.ready`.

## 2. Engaged: a graded task, never a client report

`TaskServer.isEngaged(player)` is true when `os.clock() - lastGradedAt <= 180`. `lastGradedAt` is set **only** when the server grades a valid answer: the id is the player's own open task, argument type and range are valid, the server-clock reaction is at least 0.25 s, the player is not flagged (constant reaction over 30 answers, or 20 flags per hour), and it is not a Skip nor an employee auto-resolve. Movement, jumping, chat, `Start` and any client field never set it; `TaskState` sends the display time only. "Away: tap to resume" is just a prompt to answer a task. The 3 h/day full-value cap (then 5%; the day starts at 08:00 UTC like the daily calendar) and the away bank sit in `IpoServer.addEarnings(kind)` (PR 2); this module only exposes `isEngaged` and `engagedSeconds`. Result (sim, LONG doc section 2): a macro that only sends input **never** reaches the IPO (before: 4.8 days); a perfect 24/7 task-bot needs 10.4 days (before: 2.3).

## 3. Tasks (20 rows, plus the C+D board request; seconds = of current Income)

| Task | Action | Timing | Reward | Rung |
|---|---|---|---|---|
| Customer call | click | every 20-40 s, queue 3, 8 s | **7 s** x chain; expiry resets it | Garage |
| Bugs on screen | targets | every 45-90 s, 4 bugs, 6 s | +1.5 s per hit, -1 s per bug left (max -4 s) | Seed |
| Coding (ship a feature) | timing | ready every 150 s, waits | +25% Income 60 s (14 s); slip = half | Seed |
| Interview | choose 1 of 3 | every 6-10 min, 40 s | cost 8-20 s for +10-25% 3-4 min; net 16-25 s | Seed |
| Investor pitch | choose 3 | every 8-12 min, 30 s | Funds 40 s **or** (once per run) Shares = max(1, ceil(5% of the run's base)), never doubled | A |
| Surprise event | choose the fix | every 4-7 min, 20 s | solved +6 s; unsolved -15% Income 30 s | A |
| Support ticket | choose 2 | every 40-70 s, queue 5, 12 s | 2 s each | A |
| Demo, then contract | choose, 3 rounds | every 5-9 min, 45 s | 0/15/30/45 s | A |
| Product feedback | choose 1 of 3 | every 10-15 min, 60 s | about 25 s | B |
| 1-to-1 / team pizza | choose | every 8-15 min, 90 s | morale +10% 2 min (12 s); skip free | B |
| Viral post | timing | every 6-10 min, 10 s | on time 16 s, late 3 s | B |
| Press interview | choose 3 | every 15-20 min, 45 s | 0/10/20/28 s | B |
| Ad campaign | choose a budget | ready every 10-15 min | Income given up 60 s, repaid as a shown boost; net 20 s | C+D |
| Cash crunch | choose 3 | every 15-25 min, 30 s | solved +20 s; unsolved -20% 45 s | C+D |
| Package pickup | targets | every 60-120 s, queue 2 | 2 s + 1 Office Point; every 5th box a decor piece (counter) | C+D |
| Product launch | 3 steps | ready every 20-25 min | 70 s (partial 35 s) | C+D |
| Office decoration | choose, place | any time | cosmetic, Office Points | C+D |
| Board request | choose 1 of 3 | every 45 engaged min, C+D only | **fixed** 60 s, no random reward (D9-safe) | C+D |
| Pre-IPO roadshow | 3 meetings | once per run | 3 x 40 s (valuation) | Pre-IPO |
| Paired demo | co-op timing, 2 players | invite 20 s | 90 s of **own** Income; max 3 per pair per hour | outside the 50 h path |
| Investor Day (M7) | all tasks, 20 min | weekly | x1.5; leaderboard on Investor Points; cosmetic prizes | outside the 50 h path |

## 4. Bonus, budget per rung, founder load

The task bonus `f` (Income fraction the tasks add; typical / expert / bot). With the flat budget 0.85 the three players end within 0.07 of each other at hour 40 (0.91 / 0.96 / 0.98): skill stops mattering and a bot looks like a typical player. Two fixes, with numbers:

| Rung | Hires | Budget (proposed) | f at flat 0.85 | **f at the rung's budget** | f at 0.85 if only waves 1-2 pay Income (rest: Office Points) |
|---|---|---|---|---|---|
| Garage | 2 | 0.85 | 0.32 / 0.54 / 0.52 | same | 0.32 / 0.54 / 0.54 |
| Seed | 4 | 0.85 | 0.50 / 0.65 / 0.66 | same | 0.48 / 0.68 / 0.68 |
| Series A | 7 | 0.95 | 0.70 / 0.84 / 0.87 | 0.77 / 0.90 / 0.88 | 0.75 / 0.87 / 0.87 |
| Series B | 10 | 1.05 | 0.85 / 0.91 / 0.93 | 0.91 / 1.06 / 1.08 | 0.83 / 0.91 / 0.93 |
| Series C+D | 15 | 1.15 | 0.91 / 0.95 / 0.96 | 1.05 / 1.16 / 1.20 | 0.89 / 0.94 / 0.96 |
| Pre-IPO | 18 | 1.25 | 0.91 / 0.96 / 0.98 | **1.09 / 1.24 / 1.26** | 0.92 / 0.96 / 0.97 |

**Proposal: a budget per rung** (0.85, 0.85, 0.95, 1.05, 1.15, 1.25): skill matters again (Pre-IPO spread 0.17, was 0.07). Office Points for new families does not restore it (spread 0.05). The bot gains more Income per hour but not more clock: valuation is capped per day (LONG doc section 2). Costs: PR 1 needs `B` per rung, and the first-run bonus must be measured (section 5).

**Founder load with a big team** (all tasks on, typical player, 2 h model, demand capped at D = 2.0):

| Desks | 3 | 8 | 12 | 16 | 18 | 20 |
|---|---|---|---|---|---|---|
| Founder busy | 49% | 54% | 57% | 59% | 55% | 53% |
| Founder answers /h | 330 | 362 | 419 | 404 | 388 | 366 |
| Team handles /h | 2 | 88 | 130 | 150 | 204 | 271 |
| f | 0.79 | 0.90 | 1.05 | 1.10 | 1.12 | 1.14 |

A 20-desk team does not bury the founder: busy stays at 49-59% and the team takes more of the volume. (The sim's real limit: the planned roster, not 20 distinct creatures with random rolls: check in Studio.)

## 5. Measurement hooks (in PR 1, no pay change)

Studio-only Debug buttons "Task stats" and "Set rung", a log line every 10 min per player, plus an `AnalyticsService` custom event `task_session`: rung, hires, online seconds, **engaged seconds**, graded answers, auto-resolved count, reward seconds paid, **measured f = reward seconds / engaged seconds**, budget fill (share of rewards paid at 20%), expiries, flags. **Gate G1** (LONG doc section 8): PR 1 has only calls, so the target is the **calls-only f per rung: Garage 0.32, Seed 0.37, Series A 0.41** (sim 9m), 5 players, two sessions each, at least 20 engaged minutes per session, rung set with "Set rung". Pass if measured f is within **0.8-1.2x** of the sim; below, raise the call seconds, above, lower them, and refit `f_mult` before PR 2. The all-task values (Garage 0.32, Seed 0.50) are only the PR 2+ target.

## 6. Safety and saves

- **Server authority.** The server creates each task (id, `os.clock` deadline, answer, targets) and computes the reward. It checks types, ranges, own open task, `data.ready`, not `IpoServer.isBusy`, server clock. Targets are server indexes, unhit, 0.2 s after spawn. **Rate limits:** 8 task remotes per second per player (token bucket), 40 answered tasks per minute; bad input is ignored with a warning.
- **Autoclicker.** The budget and the daily value cap are the defence; a reaction under 0.25 s, or a constant one over 30 answers, pays 0 for that task and does not count as engaged.
- **D9.** No task stakes Cash, Shares, eggs or products on a random result; "cost" is a visible deduction with a fixed result; no hidden risk rolls; rewards are never eggs, creatures or random items (decor from a counter); chance only picks which task arrives; no pass or product touches tasks, so restricted players need no `PolicyService` branch.
- **Saves (rule A10), new top-level sections only.** `tasks = { sharesRun = ipo count the Shares reward was used for, done, bestChain, seen }` (PR 1 adds it: Shut down all servers); boosts, budget and queues are not saved. Later: `office = { points, owned }`, `investorDay = { week, points }`; the LONG doc adds `away` and `lineage`. Each has `serialize`, a `KNOWN_SECTIONS` entry, optional load; **every new section needs Shut down all servers**; rollback floor `V_launch`.

## 7. UI layout spec (px, from the top-left; a phone at 320x568 and at 667x375)

Existing geometry: portrait HUD column x 12-88 (y 74-494), valuation bar y 12-76, pop-up lane y 504-552; landscape HUD row y 6-70, pop-up lane y 311-359 (daily pop-up y 255-303); windows 0.92 of the screen, max 640x470. **Touch controls to keep clear** (assumed from Roblox's defaults, check with Test > Device): thumbstick x < 170 and y > H-170; **jump button x > W-150 and y > H-130**.

| Element | Portrait 320x568 | Landscape 667x375 |
|---|---|---|
| Task tray (3 chips) | chips 68x44 at x 98-310, y 392-436 | chips 104x44 at x 176-500, y 206-250 |
| Task card (not a window) | bottom sheet 300x260 at x 10, y 236-496 | **300x220 at x 183-483, y 80-300** (right edge 34 px short of the jump zone, left edge 13 px past the thumbstick) |
| "Away: tap to resume" | 160x32 under the valuation bar, x 98-258, y 82-114; hit area 48 high | same size at x 370-530, y 76-108 |
| Away summary | dialog 300x360 centered (x 10-310, y 104-464): 4 lines of 14 px, "Collect" 280x48 at the bottom | 360x300 centered (x 153-513, y 38-338): numbers left, "Collect" 160x48 right |
| Office window (tabs Upgrades / Desks / Decor) | standard shell 294x523; tabs 40 high, 6 rows of 56 = no scrolling for one office | shell 613x345; tabs in a 110 px left column; 2 x 3 tiles of 240x84 |
| Prestige wing (a tab of the IPO shop) | 2-column tiles 140x112, 6 visible, then scroll; buy buttons 48 high | 4 x 2 tiles 128x110, no scrolling |

Rules: text 14 px or more, buttons and targets 48 px or more, at most 6 targets (2 columns in portrait); a card hides the tray, a window hides the tray and pauses expiry (30 s per task, 60 s per minute); the tray never covers the daily chip. Every PR has a screenshot check at both sizes and a Studio-only Debug button "Task: spawn".

## 8. Files and task PRs

New: `TaskConfig.lua` (ReplicatedStorage), `TaskServer.lua`, `TaskClient.lua`, `TaskGames.lua`. Changed: `TycoonCore.lua`, `OnboardingConfig.lua` (goal "Answer a call"), README, CLAUDE.md, ROADMAP, `docs/ECONOMY.md`, `tools/daily_test.py`, `tools/economy_sim.py` (keep `ACTIVE_*` equal to `TaskConfig`). Each file is claimed in CONTRIBUTING.md first. Task PRs inside the LONG doc plan: **PR 1** engine + calls + hooks, tasks Studio-only behind `TaskConfig.Enabled` (L: 1,100 Lua + 250 test); **then Studio gate G1** (calls only); tasks 2-5 in PR 5-6: bugs/coding/events (M), pitch/interviews (M, Shares slot against `ipo.count`), demo/feedback/tickets (M), marketing and 1-to-1 (M), crunch/roadshow/launch (M), pickups and decoration (M, `office`), paired demo and Investor Day (M, outside the 50 h path).

## 9. Open questions

1. **Budget per rung** (recommended, used by the sim and the LONG doc) or flat 0.85 with Office Points for new families?

Closed: calls pay 7 s of Income, not 30 s; Investor Day prizes are cosmetic only (both kept in the LONG doc); paired demo and Investor Day sit outside the 50 h path.
