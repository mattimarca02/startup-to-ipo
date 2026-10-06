# The first hour: gameplay proposal (design only)

Design only; no script, config or test changed. Line numbers are `main`'s (`e3c9e67`). Other docs: `TUT` TUTORIAL_PROPOSAL (`design-tutorial`); `CUST`, `FUND`, `SECT` the customize, funding rounds, sectors proposals (`design-sims-fixes`); `LG`, `ACTIVE` LONG_GAME and ACTIVE_LOOPS proposals; `BIBLE` CONTENT_BIBLE (`content-bible`); `SHOP_UX`, `WORLD` (`world-icons-pass`); `SIMS` SIMS_RESULTS (`sims-two-sectors-clean`); `SOUND` docs/SOUND_PLAN.md. (unverified) = not checked.

**Today** = `main`: no calls on live servers (`TaskConfig.StudioOnly`, TaskConfig.lua:25). **Launch** = today plus LONG_GAME PR 2 (first IPO after about 57 engaged hours, LG:7), calls from the Desk on (`task-needs-desk`), the tutorial, sectors, rounds and the decisions below. **Numbers:** `python3 tools/economy_sim.py` ("sim §n") and `python3 tools/first_hour_model.py`, which adds the free egg, calls and the Day 1 gift (assumptions in its header: Desk at 0:30, eggs hatched 20 s after ready, 80% of calls answered, a Garage Egg hire worth $4.97/s). Each `first-hour-model` block is its output, checked by `--check`. Model numbers are estimates, prices placeholders.

## 0. Owner decisions (2026-10-06)

All DECIDED BY THE OWNER:
- **D1** Cheaper first Garage items plus a **Desk 3** (3.3).
- **D2** **Milestones in every rung:** a title and a star on the funding sign, never Cash (3.4).
- **D3** **A two-card sector picker first**, Software preselected, Gaming second, Fintech and Biotech hidden until the second founding (8).
- **D4** **Cash and Income on the valuation bar's top line**, no separate pill (5.1).
- **D5** **Headhunter becomes a fixed effect**; which one: OWNER CHOICE (6.1).
- **D6** **Poach prices follow the egg tier** at launch (6.2).
- **D7** **No 2x offline earnings product** (6.3).
- **D8** **Sound at launch**, all through a `SoundConfig`; asset id 0 plays nothing (5, SOUND).

## 1. Audit: the first hour today

### 1.1 What happens (from the code)

- **Spawn:** facing the sign "Next: Desk $0 · Buy it in SHOP > Office" (TycoonCore.lua:231, 694-701), $0, no Income.
- **Screen:** EGGS, SHOP, TEAM, POACH, IPO (left column; a top row under 460 px: ShopClient.lua:99-113), the bar "🏚️ Garage → Seed · $0 / $1.8K" (IpoClient.lua:823-832), the chip "CLAIM" (DailyClient.lua:515-520).
- **Arrow** (OnboardingClient.lua:107-153) to the sign if the next upgrade is affordable (OnboardingServer.lua:116-119), else the egg. **Free egg:** Garage, 60 s, at the back (OnboardingConfig.lua:20; CreatureConfig.lua:25-31; EmployeeServer.lua:37-40).
- **Desk:** SHOP opens on Office (ShopClient.lua:744), "Buy Free" (:554-561), the prop pops in (TycoonCore.lua:285).
- **Calls (Studio only)** with `task-needs-desk`: 20-40 s after the Desk, 8 s to answer, 7 s of Income times a chain up to x2 (TaskConfig.lua:51-58), toast "+$7" (TaskClient.lua:249-260, 408-424).
- **Hiring:** "READY!", a "Hatch" prompt within 12 studs (EmployeeServer.lua:218-236, 531-544) or "Hatch!" in EGGS (EmployeeClient.lua:571-578); a reveal (:866-940).
- **Goals** after the first hire: "Hire 3 employees", "Reach Seed stage", no reward (OnboardingConfig.lua:30-38); the arrow ends at 1 hire and 2 upgrades (:27).
- **Poaching:** new saves are protected 15 min (CreatureConfig.lua:126) but may poach; alone: "Nobody else is in this server yet" (PoachClient.lua:505-506).
- **Daily** Day 1 = 5 min of Income, at least $300 (DailyConfig.lua:24, 38). **Offline** 50% up to 8 h (TycoonCore.lua:819-828). **IPO window:** stages, resets, Shares Shop, a board (IpoClient.lua:492-566, 754).

<!-- first-hour-model:begin -->
Today, live (model): Cash / Income at 1:00 $29 / $1, 2:00 $398 / $13, 4:00 $3,989 / $68, 5:00 $6,997 / $188, 10:00 $67,672 / $208; Neon Logo 4:20, five hires 7:10, IPO-ready 10:25. With Studio calls: first call 0:53, Seed 2:30, Garage done 3:48, IPO-ready 8:40.
<!-- first-hour-model:end -->

The sim (no free egg) has Seed at 4 min (§4) and IPO 1, 2, 3, 4 at 12, 22, 40, 71 min in one session (§6); after ~7 min only HR levels ($522,500) are left (§5).

### 1.2 Findings, most severe first

- **A1 High. No Cash or Income on screen:** the bar shows valuation (IpoClient.lua:831), Cash sits in the player list (TycoonCore.lua:717-727), hidden on phones (unverified); prices go gray (ShopClient.lua:560-563). → D4.
- **A2 High. The first pointer is a sign that does nothing** (OnboardingServer.lua:116-119; CanTouch off, TycoonCore.lua:228-230). → tutorial step 1 outlines SHOP (TUT §3).
- **A3 High (launch). Garage waits:** the planned second upgrade costs $1,100 (economy_sim.py:1068), then 8 min of nothing (3.2; ~16:00 for it without the free egg: the previous model E, not re-run); longest Garage gap 18 min (SIMS S10). → D1.
- **A4 High (today). Nothing active between purchases live:** calls are Studio only (TaskConfig.lua:25). → LONG PR 2.
- **A5 High (today). Three resets in hour one** (1.1) against 50 hours (LG:3). → LONG PR 2.
- **A6 Medium. Step 5 clashes with the Desk rule:** calls ring at once, the tutorial teaches them later (TUT:25-29); early misses start quiet mode. → step 5 on the first ring.
- **A7 Medium. Stage-ups have no moment:** a room flash and bar text (TycoonCore.lua:182-186; IpoClient.lua:826-828); only the IPO has a banner (:932-939). → stage-up card.
- **A8 Medium. Robux on a countdown during a loss:** "🛡 Shield R$ 49" with a timer (PoachClient.lua:938-959; FR-14). → drop it.
- **A9 Medium. The Day 1 gift never opens itself in session 1:** it waits for the arrow (DailyServer.lua:112-125) but gives up after 60 s (DailyClient.lua:642-654); the arrow ends at ~1:22 at best. → first pause (3.1).
- **A10 Medium. No goal after minute ~4** (OnboardingConfig.lua:35-38); with LONG "Reach Seed" reads "$300 / $197K" for 90 min. → goal chain (4).
- **A11 Medium. A missed call is silent:** `Texts.Missed` (TaskConfig.lua:129) is unused (TaskServer.lua:342-348). → "Missed" on the chip.
- **A12 Medium. Offline pay is silent:** a server print (TycoonCore.lua:826); M6b not built (ROADMAP.md:87-91). → welcome-back card, no product (D7).
- **A13 Medium (launch). Cheap poaching:** 300 s of Income, min $500 (CreatureConfig.lua:117-118): a Coding Cat $900 against a $2,300 egg (economy_sim.py:1071), a Sales Shark $6,000 against $310K (LG:43). → D6.
- **A14 Low. The free egg is behind you** (EmployeeServer.lua:37-40; TycoonCore.lua:698-700); its toast comes before loading ends (OnboardingServer.lua:95, M5 F7). → toast after ready, EGGS badge.
- **A15 Low. The hatch reveal hides ringing calls** (EmployeeClient.lua:777-781; no `OpenPanel`, TaskClient.lua:435-442). → pause calls.
- **A16 Low. "Steal your rivals' best staff"** (STORE_PAGE.md:30) needs another player; LG R3 (proposed) waits 10 engaged hours. → say when it opens (7).
- **A17 Low. The lounge door prompts Robux on touch** (ShopServer.lua:683-694). → a "See VIP" button.
- **A18 Low. Income has no feel** (TycoonCore.lua:859-871). → "+$" floaters (5).
- **A19 Low. Emoji icons** (ShopConfig.lua:38-154; EmployeeClient.lua:175-176). → SHOP_UX S3/S3b.
- **A20 Low (today). Cash piles up** once only HR is left (1.1). → LONG PR 2.

## 2. The core loop (launch, Software)

- **Every 10 s:** answer a call (every 20-40 s, faster with hires: TaskConfig.lua:53, 61-62), pulled by the ringing chip and the chain (x1.1 to x2); Cash ticks.
- **Every minute:** buy the next upgrade, egg or desk; hatch. Pulled by Cash on the bar (D4) and the Office bar "$1,234 / $1,500 · about 7 s" (SHOP_UX 3.2).
- **Every 10 min:** a milestone (D2), a goal, a new task kind. **Every session:** a funding stage, its round (Raise, Later, Skip: FUND 1), a new room. **Every day:** the gift, 3 engaged hours at full value (LG:23), a trending genre (Gaming).

*Active* play alone moves the IPO clock (LG:5) and adds about a third to Garage Income (G1 target f 0.32, LG:115). *Passive* Income is every reward's unit: a call pays 7 s of it (TaskServer.lua:254), so each purchase makes each call worth more. *Decisions* turn active Cash into Income.

**AFK against active.** Today offline pays 50% for 8 h, all valuation (TycoonCore.lua:77-78, 825). At launch engaged Cash is valuation for 3 h a day, then 5% (LG:23); idle players enter quiet mode after 90 s; idle and offline share the away bank, 10% of base Income for 2 h, 10% of it valuation (LG:24): an hour away is about 1/130 of an engaged Garage hour toward the IPO (0.1 x 0.1 against 1.32), yet its Cash still buys things. The welcome-back card says "Your startup saved $X while you were away", with no Robux (D7).

## 3. The first 10 minutes (launch, Software)

Assumes the launch build, D1-D4, the goal chain (4) and this tutorial order.

### 3.1 The script

<!-- first-hour-model:begin -->
| Time | Event (D1 run) | Tutorial, goal, reward | Cash / Income |
|---|---|---|---|
| 0:30 | Desk (free) | TUT 1; Cash on the bar | $1 / $1 |
| 0:53 | first call answered +$7 | TUT 5; goal: 3 calls | $31 / $1 |
| 1:22 | free egg hatched: hire 1 | TUT 2; goal: 3 hires | $65 / $6 |
| 1:36 | Coffee Machine $150 | TUT 4: own Cash | $46 / $8 |
| 1:54 | third call answered | goal done | $257 / $8 |
| 3:00 | Laptop $800 | goal: 3 upgrades done | $60 / $13 |
| 4:04 | Desk 2 $1,000 | TUT 3: one hire per desk | $189 / $13 |
| 4:27 | Garage Egg $400 |  | $88 / $13 |
| 5:47 | egg hatched: hire 2 | hires 2/3 | $1,221 / $18 |
| 6:23 | 10th call answered | decor: Beanbag Throne | $2,130 / $18 |
| 6:47 | milestone 1 | a star, title Side Hustler | $2,560 / $18 |
| 8:32 | Desk 3 $5,000 |  | $121 / $18 |
| 8:48 | Garage Egg $400 |  | $134 / $18 |
| 10:00 | 16 calls, 2 hires, 6 of 9 items | next: Server Rack | $1,550 / $18 |
<!-- first-hour-model:end -->

Before 0:30: the picker (D3), one tap. Step 5's move fixes A6; sources: LG:88 (3 upgrades), LG:60 (a hire per desk), BIBLE:26, 261 (Beanbag); office arranging comes with CUST PR 3. **TUT 6 (the gift)** opens 10 s after the third hire, the first pause after minute 10 (4), and speeds the Server Rack instead of minutes 2-5 (fixes A9). TUT 7-9 keep their triggers (TUT:143-146): poaching when it opens (7), the first round (FUND 8), near IPO-ready.

### 3.2 Pacing targets

<!-- first-hour-model:begin -->
| Moment (model) | Target | Today | Launch as planned | Launch with D1 |
|---|---|---|---|---|
| Desk | ≤ 0:30 | 0:30 | 0:30 | 0:30 |
| First call | ≤ 1:00 | none live | 0:53 | 0:53 |
| First hire | ≤ 1:30 | 1:22 | 1:22 | 1:22 |
| Second purchase | ≤ 2:00 | 1:01 | 5:01 | 1:36 |
| Longest wait, 0-20 min | ≤ 6:30 | 3:15 | 8:19 | 2:52 |
| Longest wait, 20 min to Seed | ≤ 15:00 | Seed before 20 min | not modelled | 17:11 |
| First milestone (today: stage) | ≤ 10:00 | 2:49 Seed | none before Seed | 6:47 |
| Third hire | ≤ 15:00 | 5:51 | none in 30 min | 10:08 |
| Seed | about 1:30:00 | 2:49 | 1:30:00 (LONG's fit) | 1:30:04 (37:02 unfitted) |
<!-- first-hour-model:end -->

D1 meets every target to minute 20, **not the late Garage:** keeping 1.5 h with the Whiteboard and Neon Logo x3.1 leaves 17-min waits after the Server Rack, milestones included (question 1).

### 3.3 D1: Garage prices (placeholders)

<!-- first-hour-model:begin -->
| D1 Garage item | LONG plan | D1 placeholder |
|---|---|---|
| Coffee Machine | $1,100 | $150 |
| Laptop | $4,200 | $800 |
| Desk 2 | $3,600 | $1,000 |
| Garage Egg | $2,300 | $400 |
| Desk 3 | none | $5,000 |
| Server Rack | $13,000 | $13,000 |
| Whiteboard | $28,000 | $87,000 |
| Neon Logo | $72,000 | $220K |
| Enter Seed at | $197K | $492K (Whiteboard, Neon Logo x3.1) |
<!-- first-hour-model:end -->

The free egg takes Desk 1, so the two bought eggs need Desks 2 and 3, one price per egg tier (LG:38); this also fixes LONG's list, which buys the first hire (economy_sim.py:1067-1077). The x3.1 is this model's, so the milestones have numbers; `economy_sim.py --long` owns the re-fit (build item 9).

### 3.4 D2: milestones in every rung (amounts placeholders)

Four per rung, at shares of the rung's valuation distance: Garage 1, 12, 30, 50% (the first before 10:00, the rest in the late waits), others LONG 4(b)'s 20, 40, 60, 80% (LG:78); thresholds = LONG_K x everything so far (LG:38), with D1's Garage. Each gives a **title** and a **star on the funding sign**, never Cash or Shares (LG:5); C+D keeps LG 4(b)'s decor and task tier. Titles avoid luck, chance and prize words (D9; the model checks); entry titles stay the bible's (BIBLE:28-224). On today's stages the Garage ones all fall inside 2 minutes: ship with LONG PR 2.

<!-- first-hour-model:begin -->
| Rung (LONG, D1 Garage) | Enters at | Milestones 1-4 (valuation) | Titles 1-4 | Next rung at |
|---|---|---|---|---|
| Garage | $0 | $4,900, $59,000, $150K, $250K | Side Hustler, Coffee Powered, Garage Hero, Ready to Raise | $492K |
| Seed | $492K | $1.8M, $3M, $4.3M, $5.5M | Pitch Practicer, Demo Day Pro, Growth Hacker, Series A Bound | $6.79M |
| Series A | $6.79M | $13M, $19M, $25M, $32M | Team Builder, Product Shipper, Market Maker, Series B Bound | $37.8M |
| Series B | $37.8M | $61M, $84M, $110M, $130M | Scale-up Boss, Campus Planner, Unicorn Tamer, Big League Ready | $153M |
| Series C+D | $153M | $310M, $470M, $620M, $780M | Global Thinker, Board Favorite, Tower Builder, Pre-IPO Bound | $938M |
| Pre-IPO | $938M | $1.1B, $1.3B, $1.5B, $1.7B | Roadshow Regular, Almost Public, Big Bell Boss, Ready for the Bell | $1.86B |

With today's IpoConfig stages instead: Garage $18, $220, $540, $900; Seed $2,700, $3,600, $4,500, $5,400; Series A $9,700, $13,000, $17,000, $20,000; Series B $35,000, $46,000, $58,000, $69,000.
<!-- first-hour-model:end -->

## 4. The first hour (launch, Software)

**Goals**, two on the card at a time (new kinds beside `employees` and `stage`, OnboardingServer.lua:136-146; keys `Hire3` and `Seed` kept):

<!-- first-hour-model:begin -->
| Goal (D1 run) | Done at |
|---|---|
| Answer 3 calls | 1:54 |
| Own 3 upgrades | 3:00 |
| Reach milestone 1 | 6:47 |
| Hire 3 employees | 10:08 |
| Get a x2 chain | 29:23 |
| Buy the Server Rack | 13:00 |
| Reach milestone 2 | 27:55 |
| Reach milestone 3 | 49:43 |
| Reach milestone 4 | 1:06:54 |
| Reach Seed | 1:30:04 |
| (not a goal) TUT 6: Day 1 gift +$6,870 | 10:18 |

| At (D1 run) | Items bought | Hires | Calls answered | Milestones | Cash / Income | Seed bar |
|---|---|---|---|---|---|---|
| 5 min | 4 of 9 | 1 | 7 | 0 | $516 / $13 | 1% |
| 20 min | 7 of 9 | 3 | 34 | 1 | $21,116 / $38 | 7% |
| 60 min | 8 of 9 | 3 | 110 | 3 | $110K / $78 | 43% |
<!-- first-hour-model:end -->

**IPO tease** (milestone 1): a dot on IPO; "The road to the bell": seven stages, "Seed: your first funding round", two empty Pokedex frames (CUST 1.4), no countdown. **The gift hook** (TUT 6): Day 2 (10 min of Income) and Day 3's Garage Egg with "Next reward in 19h 40m" (DailyConfig.lua:23-31, 61), calm text (:53-69). **Tomorrow:** Day 2-3, the away card (LG:24), a named target ("Whiteboard, about 12 min"), the next title, Seed's round, room and three tasks shown ahead (BIBLE:271), Gaming's trending genre (SECT 2.3).

**First social moment**, visual: new players are shielded 15 min (CreatureConfig.lua:126; LG R3: 10 engaged hours, LG:108); neighbors' rooms (WORLD §4), stars, titles, the board (IpoClient.lua:754); an optional "Cheer" (a clap on a neighbor's sign, no reward, rate-limited); later the paired demo (ACTIVE §3). The lounge stays paid (ShopConfig.lua:46).

**First trade-off** (after the Server Rack): the Whiteboard (+$40/s, certain) or a desk and egg once Desks 4+ exist (+$5/s on average, sim §5), each card with "pays for itself in about N min". Session 1 ends on Seed's round: Raise, Later or Skip (FUND 1), never forced.

## 5. Game feel

Effects are client-only and change no data (CLAUDE.md); phone-safe = no shake, no white flash, works muted. **Sound (D8):** each event has a `SoundConfig` slot (SOUND §1); id 0 plays nothing, so the game ships complete while the owner picks assets; no sound suggests chance or a prize reel for anything sold with Robux (D9).

| Action | Today | Visual (phone-safe version) | Slot |
|---|---|---|---|
| Buy | pop, toast (TycoonCore.lua:285; ShopClient.lua:507) | icon pops 1.08x, "+$2/s" floats, 8 sparkles (float only) | Buy, BuyRefused |
| Hatch, hire | reveal (EmployeeClient.lua:866-940) | flash at 50%, rarity burst (none); walks to its desk | Hatch, Hire |
| Call | "+$7" (TaskServer.lua:453-457); a miss: nothing (A11) | chip flies to Cash; a miss shakes, "Missed", "Chain reset" in gray | CallRing, CallAnswered, CallMissed |
| Income | nothing (A18) | Cash counts up; every 5 s a "+$X" over the top earner | IncomeTick (id 0) |
| Milestone, stage | room flash (TycoonCore.lua:182-186) | card 2.5 s "Seed! New: ..."; a star; 20 confetti (card) | StageUp |
| IPO, round | banner 4 s (IpoClient.lua:932-939); none | bell, Pokedex card (CUST 1.4); a cheque "Raised $X for Y%" | Ipo, RoundRaised |
| Poach | cards (PoachClient.lua:1145, 1183-1194) | the hire walks in or out; a shield bubble (no red flashing) | PoachWin, PoachLoss |
| Daily | "Day 1: +$300" (DailyServer.lua:129-142) | the tile flips, Cash counts up | DailyClaim |

**Employees** stroll within 3 studs of `Home` every 2-6 s, every frame, within 160 studs (EmployeeClient.lua:978-1002; FR-16). Proposed states: Work (typing bob), Stroll, React (a 0.4 s hop, once per 5 s), Rest ("Zz" in quiet mode); Coffee Capybara breaks at the Coffee Machine. **Budgets (placeholders):** walkers 20 Hz within 80 studs, on screen; 6 floating texts and one 30-particle burst at most; tweens ≤ 0.6 s; no particles at low graphics quality (unverified API).

### 5.1 D4: Cash and Income on the bar

Same size and place, so the gift chip, the Goals card and the tray tests stay (IpoClient.lua:233-256; tools/daily_test.py:3159-3176). **Row 1** (today's stage label, y 4, white): `$4,630 · +$18/s`: Cash with `ShopConfig.formatCash` below $100K ("$21,116"), `IpoConfig.formatShort` from $100K ("$110K"); Income `+$X/s`, short from $10K/s; counts up between ticks. **Row 2:** the valuation track. **Row 3** (today's info label, y 40): `🏚️ Garage → Seed · $9.3K / $492K`; multiplier and Shares only when not x1 and 0 (else in the IPO window).

**667x339** (short, HUD row): x 370, y 6, 233 px wide (667−370−10−54, IpoClient.lua:238-242), the chip at x 609; row 1 at 16 pt, row 3 about 12 pt (`TextScaled`, min 8). **320x568** (tall, left column): x 98, y 12, 158 px (320−108−54, :253); row 1 (15 characters) about 15 pt; under 200 px row 3 shows icons, "🏚️→🌱 $9.3K / $492K". Estimates: insets and safe areas not measured. **Would change** (not changed): IpoClient.lua:183-185, :196-205 (row 1), :216-225 (row 3), :823-835 (`refreshHud`, the narrow variant), and a `Changed` listener on `leaderstats.Cash` and `Income` (TycoonCore.lua:717-727) beside :952. No server change.

## 6. Monetization that feels fair (D9)

**Rules.** No Robux in the first 3 minutes and none the player didn't open: in SHOP, in context, never pop-ups, timers, badges, during a loss (FR-14) or on a touch (A17); the first prompt is the player's own tap (OWNER CHOICE: no "starter offer"). Items (ShopConfig.lua), moment, risk:
- **2x Cash** 199 (:35-42): Passes tab; ~6% shorter runs (CUST 1.5); base valuation (LG:93), so careful "forever" copy.
- **VIP** 249 (:44-51): a "See VIP" button; the lounge is a glass box with two seats (ShopServer.lua:626-680).
- **Extra Employee Slots** 149 (:53-61): the "team full" card; at launch +3 desks, up to +15% (LG:60).
- **Auto-Hatch** 199 (:63-71): after ~10 hatches; Income x0.99 (sim §3), online only (EmployeeServer.lua:813-832): "comfort".
- **Headhunter** 149 (:73-80): when poaching opens; a fixed effect (6.1).
- **Shareholder** 199 (:82-89): near IPO-ready; perks ~6% sooner (CUST 1.5).
- **Pile / Bag / Vault of Cash** 29 / 99 / 299 (:94-123): Cash tab; 10 / 45 / 180 min of Income; valuation today (ShopServer.lua:540), gifts at launch (LG:93).
- **Luck Boost** 49 (:124-136): beside a Startup or Unicorn egg with exact odds (`luckText`, SHOP_UX 3.8); hidden when restricted.
- **Instant Hatch** 25 (:137-147): 5+ min left; same roll (D9_POLICY_OPTIONS.md:20). **Poach Shield** 49 (:148-157): Defense tab; fear selling if timed (FR-14).

**A free player can always** reach every stage, IPO and sector, hatch every creature (restricted players by the fixed order, EmployeeServer.lua:258-266), earn every stamp tier (targets shrink only by pass share, CUST 1.5) and title, and claim every daily reward (DailyConfig.lua:6). **The board** ranks IPOs, then best valuation (IpoClient.lua:754), which Cash packs raise today; at launch Collection (CUST 1.6), base valuation (LG:93). **Never sold:** valuation, skips, engaged time, stamps, titles, eggs or creatures, random boxes, Gaming's work, quality or wishlists (SECT 2.8); bundles have fixed contents (LG:95).

### 6.1 D5: Headhunter as a fixed effect (the effect: OWNER CHOICE)

Today it adds 0.1 to the chance of a random PvP result (ShopConfig.lua:75-79; CreatureConfig.lua:404-410), so the buyer's gain is the victim's risk, and without `changesOdds` it is sold to restricted players (ShopConfig.lua:193-196). Cash per success on D6 prices; an attempt = 9 s negotiation + 30 s cooldown (PoachServer.lua:391, 415):

<!-- first-hour-model:begin -->
| Headhunter effect | Coding Cat $400, 60% | Bug Beetle $1,100, 50% | Sales Shark $310K, 40% | Server Sloth $780K, 30% | Attempts per hour |
|---|---|---|---|---|---|
| No pass | $667 | $2,200 | $775K | $2.6M | 92 |
| Today: +10% chance (the victim's risk too) | $571 (-14%) | $1,833 (-17%) | $620K (-20%) | $1.95M (-25%) | 92 |
| A. 20% off every poach | $533 (-20%) | $1,760 (-20%) | $620K (-20%) | $2.08M (-20%) | 92 |
| B. Negotiation 4-5 s | $667 | $2,200 | $775K | $2.6M | 104 |
| C. 50% back when a poach fails | $533 (-20%) | $1,650 (-25%) | $542K (-30%) | $1.69M (-35%) | 92 |
<!-- first-hour-model:end -->

- **A. 20% off every poach** (with the Recruiter Network perk, IpoConfig.lua:104-106: price x (1−perk) x 0.8). **Recommended:** the victim's risk and the attempt rate stay; one number, "Poaching costs 20% less"; worth about today's +10% (14-25%).
- **B. Shorter negotiation:** 13% more attempts at other players: it sells pressure.
- **C. Half back on a failure:** worth most on the hardest poaches (-35% on an Epic), tied to a random result: harder to explain.

**With A:** `ShopConfig` keeps key, id, name, price; `description` "Poaching costs 20% less.", `effect = { poachDiscount = 0.2 }`, still no `changesOdds` (now correctly: restricted players may buy it). Code: ShopServer.lua:13, 216-225, PoachServer.lua:156-161, 166, PoachClient.lua:131-137, 633-634. PUBLISH_RULES 3b (docs/PUBLISH_RULES.md:81) adds "Headhunter changes no odds, sold to everyone"; no save change, no shutdown. The questionnaire (STORE_PAGE.md:167, PREPUBLISH C9) still declares eggs and poaching (a chance-based PvP action paid with Cash; whether that is a paid random item, D9_POLICY_OPTIONS.md:15-20 does not settle: unverified), but no Robux buys a better chance.

### 6.2 D6: poach prices by egg tier (placeholders)

**Rule:** price = Income x the home egg tier's price per Income (egg price ÷ the Income of the hire LONG prices it at, LG:38), never below the egg, x the run's price scale, 2 significant digits; home tiers from `LONG_HIRE_TYPES` (economy_sim.py). At base chance a poach always costs more per Income than the egg: eggs grow you, poaching picks one creature. The Counter-Offer (50%, CreatureConfig.lua:122-123) follows.

<!-- first-hour-model:begin -->
| Home egg tier (egg at launch) | Seconds of Income | Reference and priciest hire: today → launch | Cash per success at base chance |
|---|---|---|---|
| Garage ($400) | 133 | Coding Cat $900 → $400; Memo Mole $2,700 → $1,200 | $667; $2,400 |
| Startup ($310K) | 15,500 | Sales Shark $6,000 → $310K; Server Sloth $15,000 → $780K | $775K; $2.6M |
| Scale-up ($1.4M) | 23,333 | Ledger Llama $18,000 → $1.4M; Venture Dragon $52,500 → $4.1M | $4.67M; never (Legendary) |
| Unicorn ($7.1M) | 40,571 | Growth Gecko $66,000 → $8.9M; Compliance Cobra $90,000 → $12M | rarity not set |
| Decacorn ($26M) | 86,667 | Platform Panda $114K → $33M; Closer Condor $138K → $40M | rarity not set |
| Blue-Chip ($70M) | 129,630 | Brand Badger $162K → $70M; Board Bison $186K → $80M | rarity not set |
<!-- first-hour-model:end -->

**Would change** (not changed): CreatureConfig.lua:117-118 (a per-tier table), a home tier per creature, `poachCost` (:390-393), PoachServer.lua:156-161 and the dummy (:815), the new creatures' rarities (LONG PR 3), the sims (SIMS §7 leaves poaching out).

### 6.3 D7: no 2x offline product

The welcome-back card stays free. Still planning the product (not edited): ROADMAP.md:87-91 (product :90, "doubles it once" :91; :72-73 on `content-bible`, :88-89 on `design-tutorial`), docs/M6_PLAN.md:172, :239, docs/PREPUBLISH.md:128 (row D8). docs/LONG_GAME_PROPOSAL.md never mentions it; its away bank (LG:24, 34, 94) replaces offline pay.

## 7. Frustration and safety nets

- **Quiet mode:** 3 misses or 90 s, "📞 Tap to resume" (TaskConfig.lua:92, 125); windows never count (TaskServer.lua:232). → "Calls paused", employees rest, no blame.
- **Offline:** 50% for 8 h (+2 h per Night Shift level, IpoConfig.lua:94), silent; launch 10% for 2 h (LG:24). → a card with the amount and cap, no Robux (D7).
- **Rejoin:** eggs keep hatching (EmployeeServer.lua:640), the task budget refills (PUBLISH_RULES.md:59-61). → the tutorial resumes (TUT §4).
- **Losing an employee:** 10 min shield, a 5-min Counter-Offer at 50%, one loss per 10 min, Legendaries safe (CreatureConfig.lua:114-125). → a free path ("Hatch a new hire"), no Robux (FR-14).
- **A failed save:** 3 load tries, then a kick saying progress is safe (TycoonCore.lua:79-80, 746-751); a message after 2 failed saves (:457-472). → plus a cloud icon on the bar.
- **Alone** (PoachClient.lua:506): → the Poach tab says when poaching opens; no computer rival giving employees (it bypasses R2, LG:108); Max Players 6 (PUBLISH_RULES.md:5-11).
- **Low-end phone:** rooms up to 260 parts (PLOT_VISUALS.md:34), FR-16, FR-17; the plot streams in after the teleport (WORLD §3). → section 5's budgets, stream first (unverified), short mono sounds (SOUND §3).
- **Very young players:** no text input (FULL_REVIEW.md:517). → words a 10-year-old reads (BIBLE:7), calm texts, no timed Robux, no "chance" in new copy (D9).

## 8. Sectors

**The picker (D3):** two cards, a verb and a picture each: Software "Answer customers, grow steady" (preselected), then Gaming "Make games, launch hits". Fintech and Biotech are hidden on the first founding (CUST 1.3 greys them) and appear from the second: "Found the other one after your first IPO."

**Gaming's first hour** (SECT 2.2-2.6): Bedroom Studio, a free Gaming PC, no calls; first tasks Bug Squash and Art Sprint (SECT 2.5, 5). At ~1:00 a Puzzle or Platformer Game Jam pitch; a 15-engaged-minute build (SECT 2.4), a Playtest card at 50%; at ~16-20 min **Launch** shows the Forecast tier, then Reviews ring like calls. 20 timed moments an hour against Software's 7.3 (SIMS S10). Risk: three new verbs in 20 minutes, so the Forecast is one line ("Score 64 · Solid · +6 Polish for Hit"). Tutorial: SECT 5's "Pitch your first game", "Launch it".

**Shared** (CUST 2): engine, creatures, eggs, IPO, stamps, rounds, milestones, Office, poaching, daily, HUD, sounds. **Per sector:** names, buildings, upgrades, furniture, task rows, bundles, art, the `extra` hook. **The second company** opens with "What's new": the other sector preselected; company #1 as a Pokedex card (CUST 1.4); kept employees (SECT 2.7), perks, HR, decor; seed Cash ≤ 25% of the first rung (CUST 5.1); task level +1 per IPO (TaskConfig.lua:151-153); Gold on a replay (CUST 1.5).

## 9. Measurement

**Without code**, Creator Hub gives retention (day 1, 7, 30), session length, daily players, play-through rate, revenue, payers, frame rate (unverified). **With code**, `AnalyticsService` funnel, economy and custom events (names unverified), planned in ROADMAP.md:107 and ACTIVE §5; logged on the server once per player, guarded by saved state (`onboarding.goals`, `tasks.done`, `daily`). **Funnel** (event, target placeholder): spawn, `data.ready` (TycoonCore.lua:831), 100%; first_desk, `buyUpgrade` (:272-288), 95%; first_call (TaskServer.lua:436-457), 85%; first_hire, `hatch` (EmployeeServer.lua:285-308), 85%; goal_3, `Hire3` (OnboardingServer.lua:157-158), 60%; milestone_1, 50%; seed, 25%; day2_return, 25%; first_ipo, `goPublic` (IpoServer.lua:177-243), 3% by day 30. Plus Cash in and out by source and a `first_hour` event (purchases, calls answered and missed, quiet mode).

**Retention:** day 7 brings its reward, Series A's tasks, the weekly event (ROADMAP.md:93-97). Watch day 1 ≥ 25%, day 7 ≥ 8% (placeholders); if day 1 is short, read funnel steps 2-6.

**5-friend playtest** (20 min, a phone, a fresh save, sound on). The observer only says "Play as you would at home and think out loud. I can't help." Note times: finding SHOP, the first call, hatching by window or on foot, looking at Cash, the first "what now?", taps on non-buttons, the goal card, Robux screens, muting. Then ask: what is the game about; what were you doing at the end; best and most boring moment; when were you lost; what do calls do; would you play tomorrow; anything unfair or pushy; any annoying sound.

## 10. What to build, in order

By first-hour impact; each PR claims its files first. Tags: DESIGN-ONLY, CONFIG-ONLY, CODE, ART.

| # | Change (files); size; tag | Needs; plan |
|---|---|---|
| 1 | Cash and Income on the bar, D4 (IpoClient); S; CODE | new (A1) |
| 2 | Tutorial: step 5 on the first ring, 6 after the third hire (Tutorial*, TycoonCore, ShopClient, OnboardingClient); L; CODE | 3; TUT PR A-C |
| 3 | Calls start with the Desk (Task*); S; CODE | `task-needs-desk` |
| 4 | Office ladder, 44 px targets (ShopClient); M+M; CODE | SHOP_UX S1-S2 |
| 5 | `SoundConfig` (all ids 0), player, mute, volume, caps, tests; M; CODE + CONFIG-ONLY | D8, SOUND §6 |
| 6 | Feel pack: pops, "+$" floats, missed call, stage-up card, sounds (Shop, Task, Ipo, EmployeeClient); M; CODE | 5 |
| 7 | Goal chain, goal kinds (Onboarding*); M; CODE + CONFIG-ONLY | 10 |
| 8 | Economy core: calls live, away bank; XL; CODE | G1; LG PR 2 |
| 9 | D1 prices, Desk 3, free egg in the sim; Garage re-fit, S10 re-run (economy_sim, then TycoonCore, CreatureConfig); S; CONFIG-ONLY | 8 |
| 10 | D2 milestones and titles (Ipo*); M; CODE + CONFIG-ONLY | 8; LG 4(b) |
| 11 | Welcome-back card (TycoonCore, a client); S; CODE | M6b minus its product (D7) |
| 12 | Fixes: gift at the first pause, no live Shield button, VIP button, calls pause under reveals, toast after ready; S; CODE | 2; FR-14, M5 F7 |
| 13 | Headhunter, D5 (ShopConfig, ShopServer, PoachServer, PoachClient); S; CODE + CONFIG-ONLY | owner's pick |
| 14 | Poach prices, D6 (CreatureConfig, PoachServer); S; CODE + CONFIG-ONLY | 8, LONG PR 3 |
| 15 | Sound assets, ids filled (SoundConfig); S; ART + CONFIG-ONLY | 5; SOUND §5 |
| 16 | Icons, Robux cards, storage (ShopClient, IconArt); M each; CODE + ART | CUST PR 3; SHOP_UX S3-S6 |
| 17 | Street and plot numbers (TycoonCore); S; CODE + ART | WORLD |
| 18 | Employee states, FR-16 (EmployeeClient); M; CODE + ART | FR-16 |
| 19 | Funnel events (server modules); S; CODE | 7, 10; ROADMAP M9 |
| 20 | Pokedex, buildings, placement, picker (D3), rounds; L each; CODE | 8; CUST PR 1-4b, FUND |
| 21 | Gaming: content bible (DESIGN-ONLY), then the package; L; CODE + ART | G-S, G-G; SECT 5, CUST PR 8-11 |

## 11. Open questions (most important first)

1. **The late Garage:** keeping 1.5 h by raising the Whiteboard and Neon Logo leaves 17-min waits (3.2). Recommend levels I and II for both, like Series C+D (LG:76), or a Desk 4; the sims re-fit.
2. **Headhunter's fixed effect** (D5). Recommend A, 20% off every poach.
3. **The launch Garage Egg's odds:** the model assumes today's 70/25/5 ($4.97/s); LONG moves Rares to the Startup Egg. Recommend keeping a 5% Rare so the free egg can surprise.
4. **Poaching in the first hour:** with D6 a Garage poach costs about one egg. Recommend deciding LG R3 (10 engaged hours, LG:108) with D6.
5. **The six new creatures' rarities** (their poach chances). Recommend setting them with the new egg tiers (LONG PR 3).
6. **Music:** one optional calm loop. Recommend off by default with a toggle, effects on (SOUND §1).
7. **The "Cheer"** (4). Recommend building it only if the playtest shows solo players feel alone.
8. **Extra Employee Slots = +3 desks** at launch (6). Recommend yes, capped like every desk.
