# Active loops: one task engine (proposal, design only)

Branch `active-loops`; no game code changed. Every number is a **starting value**, mirrored in `tools/economy_sim.py` (`ACTIVE_*`, section 8: `python tools/economy_sim.py --active --runs 40 --days 365`). `IpoConfig`, perks, the Shares formula (cap 2, growth 0.8), the pass multiplier (2) and `ResetHourUtc` are untouched.

## 1. The engine

`TaskServer` runs every task from one `TaskConfig` row. It is a feature module like `DailyServer` (`init(core)`, `setupPlayer`, `serialize`), plugged in by TycoonCore in the all-modules-loaded gate, after `EmployeeServer` and `IpoServer`. `TaskClient` draws; remotes `TaskRemotes` (`TaskAction`: `Answer`, `Choose`, `Hit`, `Skip`, `Start`; `TaskState` server to client).

```lua
Call = { wave = 1, role = "sales", action = "click",         -- click | choose | timing | targets
  every = {20, 40}, queue = 3, limit = 8,                    -- gap (s), max waiting, time to act (0 = waits)
  reward = { seconds = 7, chain = { step = 0.1, max = 2 } }, -- seconds of the player's current Income
  miss = 0, auto = 0.20, demand = 0.08, cooldown = 0, unlock = { stage = 0 } }
```

**Action types.** The server owns answer, clock and reward; the client sends only `{taskId, answer}`. (1) **click**: tap before `limit`. (2) **choose**: 2-3 options, numbers shown, server grades. (3) **timing**: the press must land in a server window (plus ping, max 0.3 s). (4) **targets**: the server places them; the client sends an index.

**Arrival and demand.** Gap = `U(every) / (D x R)`; `D = 1 + demand x hires` (hires = employees, 0-8; demand 0.04-0.08), so **every hire raises demand**; `R = min(1.4, 1 + 0.02 x level)`.

**Employee auto-resolve.** Roles come from `CreatureConfig` (sales, eng, ops, mkt, fin). The team takes an arrival with `A = min(0.75, 1 - (1 - auto)^n_role)`; the founder keeps at least 25%. A team-taken task pays 50% (no chain), only while the player is present, shown as one "Team handled 4 calls" line. Only **routine** tasks (calls, bugs, tickets, pickups, shipping) can be taken; **exceptions** (pitch, events, negotiation, crisis, launch) never. Calls: 1 Sales in a team of 3 give founder load `1.24 x 0.8 = x0.99`; 2 Sales in a team of 8 give `1.64 x 0.64 = x1.05`. The founder keeps about one call per 30 s, while the team handles up to 36% of a volume that grew 1.6x.

**Caps and skip.** `queue` per row (a full queue silently drops the arrival), at most 3 chips on screen. **Skip** on every task: no reward, no loss, chain kept; only an expired call breaks it. **Quiet mode:** after 3 expiries in a row or 90 s without real input, no new tasks until the player acts. An idle player gets today's game, at most 2% lost per session; nothing piles up offline.

**Difficulty.** `level = funding stage (0-4) + min(IPOs, 10)`: gaps up to x1.4 faster, limits `x max(0.65, 1 - 0.03 x level)`, odds -0.8% per level, +1 target or option per 4 levels. Rewards stay (Income already scales). First run: calls with the first hire, bugs/features/interviews at Seed, pitch, events and most wave 2 at Series A, press/ad/crisis/launch at Series B; after the first IPO all are on.

**Rewards.** Cash = `seconds x data.income.Value` (passes and IPO multiplier included, like daily Cash) via `addEarnings`: earned, so it counts toward the valuation (unlike the daily gift). Boosts: one per source, total cap +50%, not saved, none offline. **Reward budget** (economy ceiling and autoclicker wall): at most 0.85 s of Income per online second, bank 60 s; beyond it rewards pay 20%, never 0. No pay during `IpoServer.isBusy` or before `data.ready`.

**Starting numbers:** call 7 s, chain to x2, budget 0.85 / bank 60 / over 20%, auto cap 0.75 / pay 50%, demand 0.04-0.08, boost cap +50%, Shares 5%, quiet after 3 expiries / 90 s.

## 2. Tasks (20 rows; the first 17 are in the sim; seconds = of current Income)

| Task | Action | Timing | Reward | Cooldown | Wave |
|---|---|---|---|---|---|
| Customer call | click | every 20-40 s, queue 3, 8 s | **7 s** x chain; expired resets chain | none | 1 |
| Bugs on screen | targets | storm every 45-90 s, 4 bugs, 6 s | +1.5 s per hit, -1 s per bug left (max -4 s, Cash never below 0) | 45 s | 1 |
| Coding (ship a feature) | timing mini-game 10-20 s | ready every 150 s, waits | +25% Income 60 s (14 s); a slip gives half; an engineer ships it at half | 150 s | 1 |
| Investor pitch | choose 3 | every 8-12 min, 30 s, Series A+ | Funds 40 s, **or** (Series B+, once per run) Shares = max(1, ceil(5% of the run's base Shares)), never doubled | 8 min | 1 |
| Surprise event | choose the fix (3) | every 4-7 min, 20 s | solved +6 s; unsolved -15% Income 30 s (4.5 s) | 4 min | 1 |
| Interview | choose 1 of 3 (cost, boost, length shown) | every 6-10 min, 40 s | contractor: cost 8 s for +10% 4 min, up to cost 20 s for +25% 3 min; net 16-25 s | 6 min | 1 |
| Demo, then contract | choose, 3 rounds | every 5-9 min, 45 s | 0/15/30/45 s for 0-3 right | 5 min | 2 |
| Product feedback | choose 1 of 3 features | every 10-15 min, 60 s | each a different boost, about 25 s | 10 min | 2 |
| 1-to-1 / team pizza | choose | every 8-15 min, 90 s | morale +10% 2 min (12 s); skipping is free | 8 min | 2 |
| Viral post | timing | every 6-10 min, 10 s | on time 16 s, late 3 s | 6 min | 2 |
| Press interview | choose, 3 questions | every 15-20 min, 45 s, Series B+ | 0/10/20/28 s | 15 min | 2 |
| Ad campaign | choose a budget (3 tiers) | ready every 10-15 min | "budget" = Income given up 60 s (-5/-10/-20%), repaid as a shown boost; net 20 s; no Cash staked | 10 min | 2 |
| Cash crunch | choose 3 measures | every 15-25 min, 30 s, Series B+ | solved +20 s; unsolved -20% Income 45 s (9 s) | 15 min | 2 |
| Pre-IPO roadshow | 3 meetings (click, choose, timing) | once per run, at IPO-ready | 3 x 40 s (valuation); may carry the run's one Shares reward | per run | 2 |
| Support ticket / invoice | choose 2 | every 40-70 s, queue 5, 12 s | 2 s each | none | 2 |
| Product launch | timing, targets, choose (35 s) | ready every 20-25 min | 70 s (partial 35 s) | 20 min | 2 |
| Paired demo | co-op timing, 2 players | invite 20 s | 90 s of **own** Income each | 15 min, max 3 per pair per hour | 3 |
| Investor Day (M7) | all tasks, 20 min | weekly | tasks and budget x1.5; leaderboard on Investor Points (tasks x difficulty, not Cash); cosmetic prizes | weekly | 3 |
| Office decoration | choose and place | any time | cosmetic, Office Points; no income | none | 3 |
| Package pickup | targets | every 60-120 s, queue 2, 15 s | 2 s + 1 Office Point; every 5th box holds a decor piece (counter, not a roll) | none | 3 |

**Flag:** 30 s per call every 30 s would double Income by calls alone (x2-x3 with the chain); I recommend **7 s**.

## 3. Economy

- **Active vs idle (online):** typical player **x1.47-1.67 with wave 1, x1.67-1.85 with all waves**; expert x1.83-1.91; autoclicker at most x1.94 (the budget). A player who ignores tasks gets exactly today's game; offline pay is unchanged. The founder is busy 25-30% (wave 1) to 40-50% (all) of the time.
- **IPO timing** (sim, 40 seeds, median, minutes really online, typical player, no perks; brackets = today):

| Player | Tasks | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 |
|---|---|---|---|---|---|---|
| active (3 x 20 min/day) | today | 12 min | 20 min | 35 min | 60 min | 6.6 h |
| | wave 1 | 9 min | 16 min | 20 min | 60 min | 6.3 h |
| | all waves | 9 min | 15 min | 20 min | 60 min | 6.0 h |
| casual30 | all waves | 9 (12) | 15 (22) | 26 (39) | 72 (72) | 14.4 h (19.2) |
| casual (10 min/day) | all waves | 9 (10) | 10 (20) | 20 (20) | 40 (40) | 3.2 h (3.3) |

  Tasks speed up the **first hour** (first IPO 12 to 9 min; expert or bot 8.6; unlocking all at minute 0 gives 8.7). They barely move **IPO 5-10**: those are gated by logins (offline Cash clears the next stage, docs/ECONOMY.md section 5), not play minutes (question 1).
- **Shares:** formula unchanged. Only addition: one Shares reward per run (pitch **or** roadshow), 5% of the run's base, min 1, via `IpoServer.grantShares`, never doubled. IPO 1: 10 to 11; IPO 10: 83 to 89 (no pass); 365-day total +5% (no pass), +2.7% (pass).
- **Shares shop (1,770):** with the pass the whole shop takes active 125 to 115 days, casual30 96 to 74, casual 309 to 299; without it nobody finishes in a year (60% to 63%).
- **Shareholder pass is not pay-to-win on tasks:** it never touches task Shares, arrivals, limits, queues, budget, odds or auto-resolve, and no pass or product skips, auto-solves or boosts a task (Auto-Hatch does not answer calls). The 2x Cash pass multiplies task Cash like all Cash, so owners and non-owners both get the same x1.7.

## 4. Simulator

`economy_sim.py --active` adds `Player(active=None)`: **default OFF**; the default run, `--ipo` and `--daily` outputs are byte-identical to before (checked), `tools/daily_test.py` passes 658/658. A Monte Carlo of the task queue per team (one founder with reaction delay, distraction and skill; demand and auto-resolve by role; queue caps; the budget; difficulty) gives an extra Income fraction that multiplies **online** Income only. Not modelled: perks, roadshow, Investor Day, how fun a mini-game is.

## 5. Safety

- **Server authority.** The server creates each task (id, `os.clock` deadline, answer, targets) and computes the reward. It checks types, ranges, that the id is the player's own open task, `data.ready`, not `IpoServer.isBusy`, and the server clock (no answer under 0.25 s). Targets are server indexes, unhit, 0.2 s after spawn.
- **Rate limits:** 8 task remotes per second per player (token bucket), 40 answered tasks per minute; bad input is ignored with a warning.
- **Autoclicker and AFK:** the budget is the defence (bot x1.87-1.94 against expert x1.83-1.91: not worth scripting). Also: a reaction under 0.25 s, or a constant one over 30 answers, pays 0 for that task; 20 flags per hour start a 10-minute quiet mode (no ban). With no real input for 90 s the engine is quiet and auto-resolve pays nothing.
- **D9.** Cash is sold for Robux, so a task that stakes Cash on a random result would be a paid random item. (1) No task takes Cash, Shares, eggs or products as a stake for a random outcome; an interview or ad "cost" is a visible deduction with a fixed result. (2) No hidden risk rolls: "risk" is a shown trade-off or the player's own timing. (3) Rewards are never eggs, creatures or random items; decor pieces come from a counter. (4) Chance only picks which task arrives. (5) No pass or product touches tasks, so restricted players get the same game and tasks need no `PolicyService` branch. A future random reward must follow `ShopServer.isRandomRestricted`.
- **Saves (rule A10), new top-level sections only.** Waves 1-2: `tasks = { sharesRun = ipo count the Shares reward was used for, done, bestChain, seen }`; boosts, budget and queues are not saved. Wave 3: `office = { points, owned }`, `investorDay = { week, points }`. Each has `serialize`, a `KNOWN_SECTIONS` entry, optional load, bad values skipped; `sharesRun` is checked against `ipo.count` on load (stale = slot free). **Every new section needs Shut down all servers.** The rollback floor stays `V_launch`: code from M4 keeps the sections frozen, so a rollback only hides the tasks.

## 6. UI (portrait 320x568, landscape 667x375)

Tasks are **not windows**: a tray of at most 3 chips at bottom center, above the pop-up lane, clear of the HUD column, the valuation bar and the daily chip. Chips 92x44 (portrait) or 120x44 (landscape): 3 fit both. A tap opens a **card**: portrait a bottom sheet at most 300x260, landscape at most 320x230 beside the tray; no scrolling, text 14 px or more, buttons and targets 48 px or more, at most 6 targets (2 columns in portrait). While an `OpenPanel` window is open the tray hides and the server pauses expiry (30 s per task, 60 s per minute). Each PR has a screenshot check at both sizes and a Studio-only Debug button "Task: spawn" (`ShopServer.addDebugAction`).

## 7. Files and Studio scripts

New: `TaskConfig.lua` (ReplicatedStorage), `TaskServer.lua` (ServerScriptService module), `TaskClient.lua` and `TaskGames.lua` (StarterPlayerScripts; tray, then timing/targets), remotes `TaskRemotes`. Changed: `TycoonCore.lua` (require, plug in, `KNOWN_SECTIONS`), `OnboardingConfig.lua` (optional goal "Answer a call"), README, CLAUDE.md, ROADMAP, `docs/ECONOMY.md`, `tools/daily_test.py` (a test group per PR), `tools/economy_sim.py` (keep `ACTIVE_*` equal to `TaskConfig`). Not changed: `ShopServer`/`ShopConfig` (no products), `IpoServer`/`IpoConfig` (`grantShares`, `isBusy`, `addEarnings` exist), `DailyServer`, `EmployeeServer`. Each file is claimed in CONTRIBUTING.md before its PR.

## 8. Build order (one PR each)

| PR | Content | Size | Test plan |
|---|---|---|---|
| 1 | Engine + customer calls (config, server, tray, `tasks` section, budget, quiet mode, Debug spawn) | L: 1,100 lines Lua + 250 test | daily_test: validation, budget, queue, auto share, A10 load. Studio: answer, expire, skip, chain, quiet mode, IPO mid-task, rejoin, 2 clients, both phone sizes |
| 2 | Bugs + coding mini-game + surprise events | M: 600 | target and timing checks |
| 3 | Investor pitch + interviews | M: 450 | Shares slot vs `ipo.count`, pass does not double, boost cap |
| 4 | Demo/contract + product feedback + tickets/invoices | M: 500 | grading, boost stacking |
| 5 | Marketing (viral, press, ad) + 1-to-1/pizza | M: 450 | no Cash staked, net-positive rows |
| 6 | Cash crunch + roadshow + product launch | M: 450 | once per run, IPO busy |
| 7 | Package pickups + office decoration (`office`) | M: 500 | decor counter, old save loads |
| 8 | Paired demo | M: 400 | 2 clients, pair limit, own-income reward |
| 9 | Investor Day (with M7; `investorDay`) | M: 400 | weekly reset, leaderboard |

Each PR re-runs the sim; all waves stay at or below x1.9.

## 9. Open questions

1. Tasks cut the first IPO from 12 to 9 min and barely move IPO 5-10 (login-gated). Accept, or keep the first IPO near 12 (lower first-run rewards)? Faster late IPOs need an `IpoConfig` change, which I did not make.
2. Calls pay 7 s of Income, not 30 s. OK?
3. Task Cash counts toward the valuation (my pick: it is earned). Or a gift like daily Cash, which leaves IPO timing unchanged but makes tasks pay nothing toward the IPO?
4. Should the 2x Cash pass multiply task Cash (my pick: yes, same ratio for everyone)?
5. Investor Day prizes: cosmetic only (my pick), or Shares too?
