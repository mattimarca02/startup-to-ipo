# Sectors at launch: Software and Gaming (proposal, design only)

Design only (2026-10-05; revised for the S1-S10 sim findings). No script, config or test changed. Line numbers: `main` `9798388`, checked 2026-10-05. **(unverified)** = not checked in code; **(estimate)** = not measured; **(placeholder)** = sized by the sims; **G1** = needs Studio first (CUST 5.6). `CUST` = docs/CUSTOMIZE_PROPOSAL.md, `FUND` = docs/FUNDING_ROUNDS_PROPOSAL.md, `LG` = docs/LONG_GAME_PROPOSAL.md, `BIBLE` = docs/CONTENT_BIBLE.md (branch `content-bible`).

**Decided by the owner (D-G, 2026-10-05):** the game launches with **two sectors, Software/SaaS and Gaming**, each with truly different gameplay. **Fintech and Biotech are post-launch updates.** The main goal at launch is completing both launch sectors (Hall of Fame); the game goes on with higher stamps and the leaderboard. Everything in a sector relates to the real-life field.

## 0. One engine, two packages

The engine and the package are CUST section 2's split (the engine never names a sector; a test fails on a sector key in engine code): `Sector<Name>` (data and hooks) and `SectorArt<Name>` (art in PlotArt's `P(...)` format, PlotArt.lua:9-23). Sectors add to the engine: task rows with a `sector` field (`TaskConfig.Rows`; the task engine, budget, flags and engaged clock stay shared), display names and jobs for creatures and eggs (keys unchanged), and `CompanyAction("Sector", verb, token, choice)`, routed to the active sector's `verbs`.

**Hooks** (new; Software implements none and gets the defaults): `extra(data, seconds)` (income on the income loop's one `addEarnings` call, TycoonCore.lua:866; 0 for Software; CUST 2), `onTask(data, rowKey, grade)` (a graded task's project effect), `action` (a sector verb), `awayBase(data)` (the away bank's base, 2.4; default base Income), `load`/`serialize` (the sector's own state `pokedex.active.sx`, kept whole by the engine, CUST 1.2), `card(sx)` (a summary on the Pokedex card).

**Upgrades are safe across versions.** `owned` keeps any string name, known or not (TycoonCore.lua:316-322, 770-772, written back at 417-419), and `totalIncome` only counts names in `UPGRADES` (:137-145). So a rollback to Software-only code keeps a Gaming company's upgrades (they earn nothing there until forward again). Upgrade keys are unique across sectors and never reused (CLAUDE.md "Config-driven items").

## 1. Software / SaaS

**1.1 Fantasy.** A software company that sells a product businesses pay for every month. Customers call, ask for features and report bugs; you keep them happy and the subscriptions keep coming. It is today's game.

**1.2 Core loop, minute to minute.** *Reactive and steady.* Work comes to you: a call rings every 20-40 s and must be answered within 8 s (TaskConfig.lua:49-58), a chain raises the reward, a missed call breaks it. Between calls: buy the next upgrade, hatch eggs, arrange the office. From Seed on, more task kinds wake up (BIBLE:285-296): Bug Storm (tap the bugs), Ship a Feature (press in the green zone), Interview (pick 1 of 3); later support tickets, demos, Board requests (Series C+D) and the Roadshow (Pre-IPO).

**1.3 Income model.** Steady Income: upgrades plus employees (TycoonCore.lua:137-152), paid every second by the income loop (:865-866). `extra` = 0. Every number is LONG_GAME's (LG section 3). Software is the **reference** (S3).

**1.4 Tasks and the engaged rule.** The task engine as built (TaskServer, PR 1, Studio only until LONG_GAME PR 2: TaskConfig.lua:24-30). Engaged = a graded answer in the last 180 s (TaskConfig.lua:84-88; TaskServer.lua:147-148). Engaged seconds per day are counted on the daily calendar's day (08:00 UTC, `DailyConfig.dayNumber`, DailyConfig.lua:76-78; TaskServer.lua:152-156, 238). LONG_GAME PR 2 makes valuation count 100% for the first 3 engaged hours per day and 5% after (LG:23), inside `IpoServer.addEarnings(kind)`, for every sector alike.

**1.5 Buildings and objects.** BIBLE sections 1-6 are Software's package: The Garage, Co-working Loft, Downtown Floor, Campus Wing, Tech Campus (Glass Tower and Global HQ become shell upgrades of building 5, CUST 7); today's six upgrades (TycoonCore.lua:65-72) keep their keys; 36 new upgrades, 18 desks, 22 decor (BIBLE:304-361).

**1.6 Employees.** Today's names and jobs (CreatureConfig.lua:53-104, Coffee Capybara the Intern to Venture Dragon the Lead Investor), plus LONG_GAME's six (LG:60); task roles from `TaskConfig.CreatureRoles` (TaskConfig.lua:114-120).

**1.7 Shop.** Shared: passes and products (ShopConfig.lua:35-155). Software's own: BIBLE's five decor bundles (Loft, Downtown, Campus, Tower, Golden Bell), fixed contents, `id = 0`. Night Guard is shared (an engine item, LG:95).

**1.8 Anti-exploit.** Today's engine rules, unchanged: reward budget (TaskConfig.lua:78-83), minimum reaction and flags (:88, 97), rate limits (:100), engaged only from graded answers (no movement, no client report). Software adds no new rule.

## 2. Gaming studio

**2.1 Fantasy.** An indie game studio that grows into a publisher of big hits. You pick what to make, build it, playtest it, build up wishlists, launch it, read the reviews and keep it alive with updates. Real-life words throughout: genre, scope, content complete, polish, playtest, wishlists, launch, reviews, patch, seasonal event, sequel, back catalog, publisher, game expo.

**2.2 Core loop: the title cycle.** *Proactive and planned.* One title is **in development** and at most one is **live** at a time (the next one is built while the last one earns).
1. **Pitch** (a sector verb): pick a **genre** and a **scope**; the server offers 3 names from a fixed list (no free text). Today's **trending genre** comes from a published schedule (section 2.3) and is locked into the title at Pitch.
2. **Build:** a progress bar fills with **work** from the founder and the team while engaged. Two quality meters fill too: **Fun** (Art Sprint tasks, art and marketing roles) and **Polish** (Bug Squash tasks, engineers). **Sprint Review** (a sector verb) every **12 engaged minutes (G1)** of build: pick the next sprint's focus (Fun, Polish or Speed; each card shows its exact split, same total). Ignored, the last focus stays. Target: no wait over 15 minutes in Series C+D and Pre-IPO, where a Flagship build runs 90 minutes (S10).
3. **Playtest** (once per title, at 50% work): three feedback cards worked out from the meters ("Too short", "Too buggy", "Not fun yet"); the player picks one fix, whose exact effect is shown on the card.
4. **Content complete** (100% work): **Launch** unlocks. Every extra engaged minute now adds Polish, with diminishing returns. The **Launch Forecast** shows the exact score and tier at all times.
5. **Trailer** (once, optional, before Launch): a 3-beat timing task; each good beat adds wishlists.
6. **Launch:** the tier (section 2.3) sets the live game's revenue peak. **Review** messages start arriving.
7. **Live:** revenue falls as players move on (a half-life in engaged minutes). A **Live Update** (Content Patch, Seasonal Event or Balance Patch) lifts it back; each later update lifts less. When the next title launches, the old one joins the **back catalog** (a small, capped, permanent share). A Hit adds **fans** to its genre: a sequel starts with more wishlists.

**2.3 The launch outcome: deterministic (D9).** Nothing in a launch is random or sold (2.8).
- **Quality** Q (0-100) = 50 x min(1, Fun / FunTarget) + 50 x min(1, Polish / PolishTarget), plus the Playtest fix. Targets come from the scope (data).
- **Wishlists** H (0-35) = trend match +15, fans +5 per earlier Hit in the genre this company (at most +10), Trailer up to +10. **(placeholders)**
- **Score** = Q + H. **Tiers** (data): **Flop** under 50, **Solid** 50-69, **Hit** 70-89, **Smash Hit** 90+. The Forecast shows Score, tier and what is missing ("+6 Polish for Hit"). The server computes the same function when Launch is pressed; the client sends no number.
- **Trending genre** = the unlocked genres in a fixed order, indexed by `DailyConfig.dayNumber(os.time())` (DailyConfig.lua:76-78): a published schedule (today, tomorrow and the day after are shown), the same for everyone, never a roll. It changes at 08:00 UTC; a title keeps the trend it was pitched with.
- **A flop is a choice, never bad luck:** the only way to flop is to launch under the line the Forecast shows. A flop still pays (a lower peak) and still feeds the back catalog.
- **No word of chance:** texts say "Score", "Forecast", "tier", never odds, chance, luck or "%" (the D9 word check, daily_test.py:4553-4560, extends to the sector modules, CUST 6).

**2.4 Income model.** Two parts, one `addEarnings` call.
- **Base Income** from upgrades and employees, as in Software, through `totalIncome` (TycoonCore.lua:137-145). Gaming's **upgrade Incomes are lower** (fitted by S3, G1; hires keep CreatureConfig's Income).
- **Live revenue:** `SectorGaming.extra(data, 1)` = base Income (TycoonCore.lua:677-680: no passes, with the IPO multiplier) x `peak[tier] x scope x decay(t)` plus the back catalog, **capped at 0.8 x base Income (placeholder)**. `t` = engaged seconds since launch.
- **Where it is paid:** the income loop (TycoonCore.lua:865-866) adds the extra (times the Cash pass multiplier, `ShopServer.getCashMultiplier`, :151) to the Cash it already adds and to the argument of the **same** `addEarnings` call. **No new call site:** the TycoonCore count in daily_test.py:4537 stays 3. Never in offline pay (:819-827), the away bank (LG:24), `baseIncome`, or the Income stat (task rewards are seconds of `data.income.Value`, TaskServer.lua:253-254, so the extra never inflates them); the HUD shows it apart ("Live game +$X/s").
- **Away bank on the Software-equivalent base.** The bank pays 10% of base Income (LG:24); Gaming's base is lower, so check-in players were 24-32% off parity (S3, robust). It reads `awayBase(data)`: base Income with each owned Gaming upgrade counted at the Income of the Software upgrade in the same rung and slot (data, `awayIncome`, G1), hires as they are. Computed where LONG_GAME PR 2 pays the bank (LG:94, entry 2): no new call site.
- **Engaged only:** the extra is 0 unless `TaskServer.isEngaged(player)` (TaskServer.lua:674); `t` and the decay advance only then. An away player loses no revenue and gains none: the live game waits.
- **Anti-spam bound:** a title's total live revenue is capped at `k` (G1) x its build's engaged seconds x base Income, so many tiny launches never beat one finished game.

| Scope (unlock) | Typical work, engaged min | Half-life, engaged min | Peak x base: Flop / Solid / Hit / Smash |
|---|---|---|---|
| Game Jam (Garage) | 15 | 20 | 0.15 / 0.35 / 0.6 / 0.8 |
| Indie (Seed) | 30 | 30 | same x scope |
| Mid-size (Series A) | 45 | 40 | same x scope |
| Big (Series B) | 60 | 50 | same x scope |
| Flagship (Series C+D, Pre-IPO) | 90 | 60 | same x scope |

All **G1** (S3, S9). Updates restore the curve to 70 / 60 / 50% of the peak, one per 10 engaged minutes; the back catalog adds 3% of a sunset title's peak, total at most 10% of base Income.

**2.5 Tasks and active play.** Gaming rows in `TaskConfig.Rows` (TaskConfig.lua:49) with `sector = "Gaming"`, using the engine's four actions (`click`, `choose`, `timing`, `targets`, TaskConfig.lua:35) and its budget, flags and quiet mode unchanged. A row's Cash still pays through TaskServer's one call (TaskServer.lua:257); its project effect goes through `onTask` (points, never Cash).

| Row (key) | Action | When | Role (team may take it) | Effect |
|---|---|---|---|---|
| Review | click | a title is live | sales (community) | 5 s of Income, chain like calls |
| BugSquash | targets | building | eng | Polish, 3 s of Income |
| ArtSprint | timing | building | mkt (art) | Fun, 3 s of Income |
| Playtest | choose | once per title | never | the fix shown on the card |
| Trailer | timing | once per title | never | wishlists |
| PublisherRequest | choose | Series C+D, every 45 min | never | fixed 60 s of Income (like the Board request, LG:79) |
| Expo | choose / timing / targets | Pre-IPO, once per run | never | like the Roadshow (BIBLE:296) |

- **Engaged** comes only from graded answers (TaskConfig.lua:84-88). **Pitch, Sprint Review, Launch and Live Update are sector verbs, not tasks: they never make a player engaged** (a macro spamming them gets nothing).
- **Team work:** routine rows can be taken by the team (`auto`, `AutoCap` 0.75, TaskConfig.lua:63-65); team-taken rows give points at the `teamPays` share, and only while the player is engaged.
- **3 h/day:** Cash and project points are paid in full all day, as in Software; only the valuation is weighted (LG:23, inside `addEarnings(kind)`), so both sectors lose the same after 3 h. The live curve, the build and the engaged counter (`tasks.engagedDay`/`engagedSeconds`, TaskServer.lua:152-156) do not reset at 08:00 UTC; only the trending genre changes there.

**2.6 Buildings and objects** (example names; the full list is a Gaming content bible, section 5).
- **Buildings (5, CUST defaults):** Bedroom Studio (Garage), Indie Loft (Seed), Studio Floor (Series A), Game Campus (Series B), Mega Studio (Series C+D to IPO-ready), with Motion-Capture Stage and Global Publishing HQ as shell upgrades (the 7 LONG_GAME offices on 5 footprints, CUST 7).
- **Upgrades, Garage:** Gaming PC (free, first), Drawing Tablet, Headset Mic, Dev Kit, Test Couch, Pixel Sign. Later: Sound Booth (Seed), Render Farm (A), Esports Stage (B), Global Servers (C+D, levels I and II), Golden Joystick Award (Pre-IPO).
- **Desks:** Folding-Table Desk, Gamer-Chair Desk, Crunch Pod, Dev-Kit Bench. **Decor:** Retro Console Shelf, Mascot Cutout, Cartridge Wall, Arcade Cabinet, Pixel Plant.
- **Genres (6):** Puzzle and Platformer (Garage), Racing (Seed), Sports (Series A), Adventure (Series B), Online World (Series C+D). **Game names:** a fixed list per genre ("Block Drop Deluxe", "Jumpy Jelly", "Turbo Turtle Rally", "Goal Goats", "Dungeon Dumplings", "Sky Island Online").
- **Events (fixed outcome, like BIBLE:8):** Build Won't Compile (✔ Read the error), Launch-Day Queue (✔ Add servers), Save-File Bug (✔ Roll back the patch).

**2.7 Employees: same bodies, new names and jobs.** Keys, rarities, Income and looks are CreatureConfig's (CreatureConfig.lua:53-104); only the display name and job come from `SectorGaming`, so an employee that follows the player shows the active company's name. Task roles stay `TaskConfig.CreatureRoles` (TaskConfig.lua:114-120).

CoffeeCapybara: Crunch Capybara, Studio Intern (snacks for the team); CodingCat: Gameplay Cat, Gameplay Programmer; PixelPigeon: Pixel Pigeon, Pixel Artist; HustleHamster: Hype Hamster, Community Manager; BugBeetle: Bug Beetle, QA Tester; MemoMole: Map Mole, Level Designer; SalesShark: Streamer Shark, Partnerships Lead; PitchParrot: Trailer Parrot, Trailer Director; ServerSloth: Server Sloth, Online Engineer; LedgerLlama: Producer Llama, Producer; UnicornCEO: Unicorn Director, Studio Director; VentureDragon: Publisher Dragon, Publisher; LONG_GAME's six (LG:60): Live-Ops Gecko, Ratings Cobra, Engine Panda, Console Condor, Franchise Badger, Board Bison (Live Ops, Age Ratings, Engine, Platform Deals, Franchise, Board).

**Eggs** keep their keys and odds; Gaming display names: Jam, Indie, Studio, Franchise, AAA and Legend Egg.

**2.8 Shop.**
- **Shared, unchanged:** the passes and products (ShopConfig.lua:35-155); Luck Boost stays an egg item (`changesOdds`, :134; never for restricted players, :191-195).
- **Gaming's own:** decor bundles with fixed contents, `id = 0`: Arcade Corner, Retro Shelf, Streamer Setup, Expo Booth, Launch Party.
- **Never sold, for Robux or Cash bought with Robux, in any form:** work, Fun, Polish, wishlists, a tier, a trend change, a Forecast, a build skip, an extra update. The 2x Cash pass doubles live revenue's **Cash** like any Income, never its valuation (base, LG:93) or a score.
- **Dev speed counts heads, not rarity:** work per second = founder + a fixed amount per working employee of the right role (desk-capped, LG:60). A Luck Boost (odds of a better creature) therefore never moves a launch score. Instant Hatch can bring a head sooner (speed, as it does for Software's Income), never a better tier than waiting gives.

**2.9 Anti-exploit** (server checks; each a test).
- **Requests:** `CompanyAction("Sector", verb, token, choice)`: `verb` from the sector's list, `token` = the title number (stale = refused, like `ipoNumber`, IpoServer.lua:179), `choice` a whole number in range; `data.ready`; 2 verbs per second; no yield between check and write. No time, score or amount is ever read.
- **Launch-spam:** the per-title revenue cap (2.4) and minimum work per scope. *Test:* ten Jam launches pay no more than one finished Jam of the same build time.
- **Update-spam:** one per 10 engaged minutes, each lifts less; *test:* the 4th update in a row lifts less than the 3rd. **Sprint Review:** one per 12 engaged minutes, token = title and sprint number; *test:* a stale one is refused, every focus pays the same total.
- **Idle and macros:** extra, decay and build need engaged; verbs never set engaged. *Test:* 1 h of verbs with no graded task: extra 0, work 0.
- **Task-bots:** the reward budget (TaskConfig.lua:78-83) also caps project points per engaged minute; flagged answers (:97) give no points.
- **Trend fishing:** nothing to fish: the schedule is public and locked at Pitch; cancelling a title loses its work.
- **Rejoin / crash:** `sx` is saved with the rest (one payload, one key, TycoonCore.lua:421-433, 505); the session budget note (PUBLISH_RULES.md:59-61) applies to Gaming rows too.
- **Studio:** Debug rows "Gaming: finish build", "Gaming: set day" only through `ShopServer.addDebugAction` inside `RunService:IsStudio()`, and they set `pokedex.studio`.
- **Rollback:** older code keeps `pokedex` whole (CUST 1.2) and Gaming upgrades in `owned` (section 0); it pays no extra.

**2.10 Garage to IPO, and how long.** The valuation ladder, thresholds, rounds and IPO are the shared engine's (IpoConfig.lua:17-23; LONG_GAME's 7 stages). Valuation rises from base Income plus live revenue, so it climbs in waves after each launch. Titles per rung at the typical cycle (S3, measured): Garage 4, Seed 7, Series A 8, Series B 7, Series C+D 14, Pre-IPO 9: **49 titles to IPO 1** (G1). At the IPO the title in development and the live title end (no refund), `sx` starts empty, and the card keeps titles shipped, Hits and the best tier.

**Length versus Software** (regular player, IPO 1; Software 57 h, LG:7). Fit target: the "Hit" policy equals Software ±5% (S3); the others follow by division from rates relative to Software (fitted base 0.77, extra 0.08-0.36); hours **G1**:

| Gaming policy | Average extra (x base) | Rate vs Software | IPO 1 hours (estimate) |
|---|---|---|---|
| Polish to Smash, every update | 0.36 | 1.05 | 54 |
| Polish to Hit (typical; the fit) | 0.30 | 1.00 | **57** |
| Ship at content complete (Solid) | 0.18 | 0.91 | 63 |
| Rush every title (Flop) | 0.08 | 0.83 | 69 |
| Never ship | 0 | 0.77 | 74 |

Loops 2 and 3 follow LONG_GAME's growth (51.5 / 52 h for Software, LG:18) with the same ratios. Weeks to IPO 1 are LONG_GAME's (LG:16) for the typical policy.

## 3. Side by side

| | Software | Gaming |
|---|---|---|
| Tempo | reactive: tasks arrive every 20-40 s | planned: a decision every few minutes, a title every 20-135 min |
| Money | steady Income | base Income plus launch waves |
| Main choice | which upgrade, answer or skip | genre, scope, ship now or polish, update or next title |
| Skill | reaction and chains | preparation and timing of launches |
| New engine use | none | `extra`, `sx`, sector verbs, `onTask` |

## 4. What the sims must measure (tools/economy_sim.py, `--pokedex` and new `--gaming`; marks are placeholders)

- **S3 parity:** Software and Gaming (typical policy) within ±5% per engaged hour, at every rung and every `LONG_PLAYERS` profile (check-in with 2.4's bank); fits Gaming's upgrade Incomes.
- **S4 bots, S5 hopping** (CUST 5.5) with two sectors: no sector faster for a task-bot; alternating Software and Gaming for 10 IPOs within 3% of staying in one.
- **S9 launch policy (new):** the five policies above per profile: Smash ≤ 5% faster than Software; Solid ≤ 12% slower; Flop ≤ 25% slower (a flop never ruins a run); launch-spam gains ≤ 1%; update timing best-versus-worst ≤ 5%.
- **S10 cadence (new):** moments per hour per rung for both sectors (LG section 4's table): no gap over 45 engaged minutes; Gaming's longest wait between decisions under 15 minutes (with Sprint Reviews).
- **S8** with both sectors (FUND 6).
- *Can:* `--long` (`long_run`, economy_sim.py:1213) runs Software's ladder. *Needs:* a Gaming income path (base, curve, cap, catalog), titles and policies, the trend schedule, the task points.

## 5. Impact on other docs (exact sections)

**`design-tutorial`, docs/TUTORIAL_PROPOSAL.md** (`TUT:` = its line):
- **Section 2, steps 1 and 4 (TUT:25, 28):** "own your sector's first upgrade" (Software Desk, Gaming Gaming PC) and "own 2 of this company's upgrades" (CUST 7).
- **Step 5 (TUT:29):** "one task graded by `TaskServer`", any row of the active sector; the card text comes from the sector (Software: a call; Gaming: Bug Squash or Art Sprint, as Reviews need a live title). Still skipped while tasks are off (TUT:43).
- **New Gaming-only steps after step 5:** "Pitch your first game" (done when `sx.n` ≥ 1) and "Launch it" (done when a title is shipped), server-graded, no reward. `TutorialConfig` steps gain a `sector` field (none = every sector).
- **Step 8 (TUT:32):** no sector change (FUND 8). **Step 9 (TUT:33, notes :37-42):** resets add Gaming's title in development and live title.
- **Section 6 (TUT:106):** module order unchanged by sectors.

**`content-bible`, docs/CONTENT_BIBLE.md** (`BIBLE:`):
- **Sections 1-6 (BIBLE:12-241)** are Software's package; the industry skins (:247) go (CUST 7).
- **"The first 5 hours" (:253-283), "What each rung adds" (:285-296), "Approve or rename" (:298-361)** are Software's. Gaming needs all three (a section 7 or its own file): **about 214 names (estimate)**: 7 offices, 42 upgrades, 18 desks, 18 creature names and jobs, 6 egg names, 22 decor, 5 bundles, 9 titles, 12 events, 8 publisher requests, 6 groups of 8 review lines, 6 genres, 36 game names, 7 task names, 12 company names; game names checked against real games.
- **Choice 1 (:365):** creature keys stay locked; Gaming names are display strings, not a save migration. **Choice 9 (:373)** is replaced by sectors.

**docs/LONG_GAME_PROPOSAL.md** (`LG:`):
- **Section 1, pacing (LG:6-18):** the hours are Software's fit; Gaming's typical policy must match within ±5%, the others spread 54-74 h at IPO 1 (2.10, G1).
- **Section 2, clock (LG:20-34):** Gaming's extra is engaged only and outside the away bank (LG:24); the bank reads `awayBase` (2.4).
- **Section 3, ladder (LG:36-60):** one ladder for both; Gaming has its own item names and lower upgrade Incomes (S3); the hire list is shared.
- **Section 4, content (LG:62-82):** the moments table per sector (S10); "an industry skin per IPO" (LG:82) becomes the sector picker.
- **Section 5, Shares (LG:84-88):** Shares per IPO are sector-neutral. Stamps with two sectors: 6 grades (Bronze, Gold, Platinum each), Collection at most 6,000 + IPO count, bonus at most +5% (CUST 5.2); T (CUST 1.5, G1) is shared while parity holds.
- **Section 6, money (LG:90-95):** entry (1) of the `addEarnings` list (LG:94) carries Gaming's extra (no new entry); Gaming bundles join LG:95's product list.
- **Section 8, PR plan (LG:110-122):** its PR 7 = PR 8-11 in CUST 6; Gaming needs its PR 2 (`kind`, engaged weights).

## 6. Open questions (unresolved, most important first)

1. **If G-G fails** (CUST 6): delay the launch until Gaming passes, or launch with Software alone and Gaming as the first update?
2. **Is Software different enough** as today's reactive loop, or does it need a SaaS mechanic of its own (subscribers, uptime)? Recommend: keep it; ask the G-S players.
3. **Where the Project window opens on a phone:** a sixth HUD slot shown only in Gaming (the top row grows from 370 to 442 px, IpoClient.lua:237-238; fit **unverified**), or a tray chip? Recommend the HUD slot.
4. **A live game while away:** waits (designed) or loses players in real time (more real, punishes breaks)?
5. **Words for kids:** "Flop" and "crunch" are real industry words; keep them, or "Quiet launch" and no crunch names?
6. **Trend schedule:** a new trending genre every day (designed) or every week?

## What I did not verify

- The sims were not re-run here; their findings were taken as given. Every Gaming number is a placeholder; G1 ones need Studio first (CUST 5.6).
- Fun, the phone layout of a Project window and where it opens from were not tested; no Studio or MCP was used.
- BIBLE and LONG_GAME's item list were read, not rebuilt; Gaming names are examples, not checked against real brands beyond the author's reading.
