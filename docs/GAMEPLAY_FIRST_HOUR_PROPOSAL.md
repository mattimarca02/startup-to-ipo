# The first hour: gameplay proposal (design only)

Design only (2026-10-06, branch `gameplay-design`, from `main` `e3c9e67`). No script, config or test changed. Line numbers are `main`'s. Other branches' docs: `TUT` docs/TUTORIAL_PROPOSAL.md (`design-tutorial`); `CUST`, `FUND`, `SECT` the customize, funding rounds and sectors proposals (`design-sims-fixes`, newer than `main`); `LG` docs/LONG_GAME_PROPOSAL.md; `BIBLE` docs/CONTENT_BIBLE.md (`content-bible`); `SHOP_UX`, `WORLD` (`world-icons-pass`); `SIMS` docs/SIMS_RESULTS.md (`sims-two-sectors-clean`). **(estimate)** = my model, **(placeholder)** = for the sims to size, **(unverified)** = not checked.

**Today** = `main`: live servers have no calls (`TaskConfig.StudioOnly`, TaskConfig.lua:25). **Launch** = today plus the decided plans: LONG_GAME PR 2 (first IPO after about 57 engaged hours, LG:7), calls from the Desk on (`task-needs-desk`), the tutorial, sectors and rounds. Numbers: `python tools/economy_sim.py` ("sim §n") and a scratch model with the same config numbers plus human delays (Desk at 0:30, a ready egg noticed in 20 s, 80% of calls answered: estimates).

## 1. Audit: the first hour today

### 1.1 What happens (from the code)

- **Spawn:** the player lands in the garage facing the sign "Next: Desk $0 · Buy it in SHOP > Office" (TycoonCore.lua:231, 694-701) with $0 and no Income.
- **Screen:** five emoji buttons EGGS, SHOP, TEAM, POACH, IPO (a left column, a top row under 460 px: ShopClient.lua:99-113), the valuation bar "🏚️ Garage → Seed · $0 / $1.8K" (IpoClient.lua:824-832), the gift chip "CLAIM" (DailyClient.lua:515-520).
- **Arrow:** a beam and a bouncing chevron (OnboardingClient.lua:107-153) toward the sign while the next upgrade is affordable (OnboardingServer.lua:116-119), else the egg.
- **Free egg:** a Garage Egg, 60 s, in an incubator at the back of the plot (OnboardingConfig.lua:20; CreatureConfig.lua:25-31; EmployeeServer.lua:37-40).
- **Desk:** SHOP opens on Office (ShopClient.lua:744), "Buy Free" (:554-561), toast "Bought Desk", the prop pops in (TycoonCore.lua:285).
- **Calls (Studio):** from 20-40 s after the Desk, 8 s to answer, 7 s of Income times a chain up to x2 (TaskConfig.lua:49-58), toast "+$7" (TaskClient.lua:249-260, 408-424).
- **Hiring:** "READY!" and a "Hatch" prompt within 12 studs (EmployeeServer.lua:218-236, 531-544) or "Hatch!" in EGGS (EmployeeClient.lua:571-578); a wobble-flash reveal (:866-940).
- **Goals:** after the first hire, "Hire 3 employees" and "Reach Seed stage", no reward (OnboardingConfig.lua:30-38); the arrow ends at 1 hire and 2 upgrades (:27).
- **Poaching:** a new save is protected 15 min (CreatureConfig.lua:126) but may poach; alone: "Nobody else is in this server yet" (PoachClient.lua:505-506).
- **Daily:** Day 1 = 5 min of Income, at least $300 (DailyConfig.lua:24, 38).
- **IPO window:** stages, resets and keeps, Shares Shop, an in-server board "most IPOs first, then the best valuation" (IpoClient.lua:492-566, 754).
- **Quiet mode:** 3 misses or 90 s without an answer: "📞 Tap to resume" (TaskConfig.lua:92, 125).
- **Offline:** 50% of Income for up to 8 h, paid at join (TycoonCore.lua:819-828).

### 1.2 Minute by minute (today, a typical new player; model estimates unless marked sim)

| Time | Does and sees | Cash / Income live | With calls (Studio) |
|---|---|---|---|
| 0:00 | Reads the sign, walks to it | $0 / $0 | same |
| 0:30 | Finds SHOP, gets the Desk | $0 / $1 | first call 0:53, +$7 |
| 1:01 | Coffee Machine ($25) | $29 / $1 → $3 | 0:59 |
| 1:22 | Hatches the free egg, goal card | $8 (egg average $5.0/s, sim §5) | same |
| 2:00 | Laptop, Server Rack | $398 / $13 | |
| 2:49 | **Seed**: the room flashes, no message | | 2:30 |
| 3:03-4:20 | Whiteboard, Neon Logo: garage done | $3,989 / $68 at 4:00 | done 3:48 |
| 4:25-7:10 | Garage Eggs to the 5-hire cap | $6,997 / $188 at 5:00 | |
| 7:00-10:00 | Nothing new to buy | $67,672 / $208 at 10:00 | |
| 10:25 | **IPO-ready** | | 8:40 |
| 12 / 20 / 35 / 60 min | IPO 1 / 2 / 3 / 5 (sim §6) | | |

The sim has no free egg: Seed at 4 min, IPO-ready at 12 (sim §4).

### 1.3 Findings, most severe first

| # | Finding (evidence) | Sev. | Fix idea |
|---|---|---|---|
| A1 | **Cash and Income are not on screen.** The bar shows valuation (IpoClient.lua:831); Cash lives in Roblox's player list (TycoonCore.lua:717-727), hidden on phones (unverified). Office prices just go gray (ShopClient.lua:560-563). | High | Cash and +$/s on the bar; Office progress bar (SHOP_UX 3.2) |
| A2 | **The first pointer is a sign that does nothing** (OnboardingServer.lua:116-119; CanTouch off, TycoonCore.lua:228-230). Nothing outlines SHOP. | High | Tutorial step 1 outlines SHOP, then Office (TUT §3) |
| A3 | **Launch Garage waits.** The second upgrade costs $1,100 (economy_sim.py:1068): ~5:00 with the free egg, ~16:00 without, then nothing until Desk 2 at ~13:00 (model). Longest Garage gap 18 min (SIMS S10). | High (launch) | Placeholder prices, section 3 |
| A4 | **Live: nothing active between purchases.** Calls are Studio only (TaskConfig.lua:25): after ~7 min the player waits. | High (today) | LONG PR 2 (planned) |
| A5 | **Too much too early.** Seed ~3-4 min, IPO 1 at 12, IPO 3 at 35 (sim §6): three resets in hour one, against 50 hours (LG:3). | High (today) | LONG PR 2 (planned) |
| A6 | **Step 5 clashes with the Desk rule.** Calls ring right after the Desk; the tutorial teaches them after hatching and a second upgrade (TUT:25-29). Early calls expire; 3 misses start quiet mode. | Medium | Step 5 on the first ring |
| A7 | **Stage-ups have no moment:** a room flash and new bar text (TycoonCore.lua:182-186; IpoClient.lua:826-828); only the IPO gets a banner (:932-939). | Medium | Stage-up card |
| A8 | **Robux on a countdown during a loss:** "🛡 Shield R$ 49" with a timer bar in the live poach alert (PoachClient.lua:938-959; FR-14). | Medium | Drop it (FR-14's fix) |
| A9 | **The Day 1 gift never opens by itself in session 1:** it waits for the arrow to end (DailyServer.lua:112-125) but gives up 60 s after joining (DailyClient.lua:642-654); the arrow ends at ~1:22 at best. | Medium | Open it at the first pause |
| A10 | **No goal after minute ~4:** two goals (OnboardingConfig.lua:35-38). With LONG, "Reach Seed" reads "$300 / $197K" for 90 min. | Medium | Goal chain, section 4 |
| A11 | **A missed call is silent:** `Texts.Missed` (TaskConfig.lua:129) is never used; the chain resets quietly (TaskServer.lua:342-348). | Medium | "Missed" on the chip, "Chain reset" |
| A12 | **Offline pay is silent:** a server print only (TycoonCore.lua:826); M6b not built (ROADMAP.md:87-91). | Medium | Welcome-back card |
| A13 | **Launch poaching is cheap:** 300 s of Income, min $500 (CreatureConfig.lua:117-118): a Coding Cat costs $900, its egg $2,300 (economy_sim.py:1071). Not simulated (SIMS §7). | Medium (launch) | Price poaches from the egg tier |
| A14 | **The free egg is behind you** (EmployeeServer.lua:37-40; spawn faces front, TycoonCore.lua:698-700); its toast is sent before loading ends (OnboardingServer.lua:95, M5 F7). | Low | Toast after ready; timer badge on EGGS |
| A15 | **The hatch reveal hides ringing calls:** it covers the tray (EmployeeClient.lua:777-781) without `OpenPanel`, so calls keep running (TaskClient.lua:435-442). | Low | Pause calls during reveals |
| A16 | **A store promise solo players can't use:** "steal your rivals' best staff" (STORE_PAGE.md:30) needs another player; LG R3 (proposed) also waits 10 engaged hours. | Low | Say when it opens (section 7) |
| A17 | **The lounge door opens a Robux prompt on touch** (ShopServer.lua:683-694). | Low | A "See VIP" button |
| A18 | **Income has no feel:** the loop only changes numbers (TycoonCore.lua:859-871). | Low | "+$" floaters (section 5) |
| A19 | **Emoji icons** everywhere (ShopConfig.lua:38-154; EmployeeClient.lua:175-176). | Low | SHOP_UX S3/S3b (planned) |
| A20 | **Today Cash piles up:** after ~7 min only HR levels ($522,500) are left (sim §5). | Low (today) | LONG PR 2 (planned) |

## 2. The core loop (launch, Software)

| Every | The player | Pulled by |
|---|---|---|
| 10 s | Answers a call (every 20-40 s, faster with more hires: TaskConfig.lua:53, 61-62); Cash ticks | the ringing chip, the chain (x1.1 to x2) |
| minute | Buys the next upgrade, egg or desk; hatches | the Office bar "$1,234 / $1,500 · about 7 s" (SHOP_UX 3.2) |
| 10 min | A milestone: decor, title, a goal, a new task kind | the goal card |
| session | A funding stage, its round (Raise, Later, Skip: FUND 1), a new room | the valuation bar |
| day | The gift, 3 engaged hours at full value (LG:23), a trending genre (Gaming) | the calendar, the away bank |

**Three layers, one loop.** *Active* play (calls, later events and pitches) is the only thing that moves the IPO clock (LG:5) and adds about a third to Income in the Garage (G1 target f 0.32, LG:115). *Passive* Income (upgrades, hires) is the unit every reward is paid in: a call pays 7 s of Income (TaskServer.lua:254), so every purchase makes every call worth more. *Decisions* (which upgrade, egg or desk; raise or skip) turn active Cash into passive Income. Answer, buy, earn more per answer, see the next price: that is the game.

**AFK against active.**

| | Active (answers calls) | Online, not answering | Offline |
|---|---|---|---|
| Today | Income (no calls live) | the same Income | 50% for 8 h, all valuation (TycoonCore.lua:77-78, 825) |
| Launch | Income + calls, valuation 100% for 3 h a day, then 5% (LG:23) | quiet mode after 90 s (TaskConfig.lua:92); the away bank: 10% of base Income, 2 h, 10% of it valuation (LG:24) | the same away bank |

An hour away is worth about 1/130 of an engaged Garage hour toward the IPO (0.1 x 0.1 against 1.32, estimate), but its Cash still buys the next item. The welcome-back card (section 5) says so calmly: "Your startup saved $X while you were away."

## 3. The first 10 minutes (launch, Software)

Assumes the launch build plus this doc's proposals: placeholder Garage prices (3.3), Cash on the bar (A1), the goal chain (section 4), Garage milestones (3.3). Cash and Income are a model (estimates). Sounds are optional; the game is complete without them (section 5).

### 3.1 The script

| Time | Sees, hears | Does | Cash / Income | Tutorial and goal card |
|---|---|---|---|---|
| 0:00 | Sector picker, Software preselected (CUST 1.3; OWNER CHOICE) | Taps Start | $0 / $0 | none |
| 0:10 | Garage; SHOP outlined; Office hero "Get it free" | Gets the Desk: "+$1/s" floats, a coin sound | $0 / $1 | **TUT 1** |
| 0:30-0:55 | The desk phone rings (20-40 s after the Desk, TaskConfig.lua:53) | Answers: "+$7", chain x1.1 | $36 / $1 | **TUT 5 moved here** (fixes A6); goal "Answer 3 calls" |
| 1:00-1:22 | EGGS badge "READY", arrow to the incubator | Hatches: reveal, first hire | $167 / $6 at 2:00 | **TUT 2**; goal "Hire 3 employees 1/3" |
| 1:43 | Hero bar full, a soft pulse | **First purchase with own Cash:** Coffee Machine $150 | | **TUT 4** |
| 2:00-3:30 | Calls every ~25 s, the chain grows | Answers, saves | $581 / $6 at 3:00 | "Answer 3 calls" ✓ |
| 3:34 | | Laptop $800 | / $11 | "Own 3 upgrades" ✓ (LG:88) |
| 4:51-5:21 | TEAM "1/1 desks" | Desk 2 ($1,000), an egg ($400) | | **TUT 3** rewritten: one hire per desk (LG:60) |
| 6:41 | Reveal | Second hire | $1,465 / $14 at 7:00 | "Hire 3 employees 2/3" |
| ~7:00 | 10th call answered | Decor: Beanbag Throne (BIBLE:26, 261) | | |
| ~8:00 | **Milestone 1** ($5K valuation): the funding sign gets a star, a short fanfare | Desk 3 ($2,500); title "Garage Dreamer" (BIBLE:28) | | "Reach milestone 1" ✓ |
| 10:00 | Next target "Bug Beetle egg · about 1 min" | Calls; arranges the office (CUST, after PR 3) | $2,130 / $14 | |

TUT 6 (the gift) comes at the first pause after minute 10, the third hire (~12:20): Day 1 is 5 min of Income (~$6,600 at $22/s), so it fills the longest wait (12:21 to the Server Rack at 19:04) instead of rushing minutes 2-5 (fixes A9). TUT 7-9 wait for their own triggers (TUT:143-146): poaching when it opens (section 7), funding at the first round (FUND 8), going public near IPO-ready.

### 3.2 Pacing targets

| Moment | Target | Today (model A) | Launch as planned (model D) | With 3.3 (model G2) |
|---|---|---|---|---|
| Desk | ≤ 0:30 | 0:30 | 0:30 | 0:30 |
| First call | ≤ 1:00 | none live | 0:53 | 0:53 |
| First hire | ≤ 1:30 | 1:22 (sim, no free egg: 5 min) | 1:22 | 1:22 |
| Second purchase | ≤ 2:00 | 1:01 | **5:01** | 1:43 |
| Longest wait for a purchase or unlock, 0-20 min | ≤ 6:00 | 3:15 | **8:19** | 6:09 |
| First milestone | ≤ 10:00 | Seed 2:49 (too early) | none before Seed | 8:02 |
| Third hire | ≤ 15:00 | 5:51 | none in 30 min | 12:21 |
| First Seed | inside session 1 | 4 min (sim §4) | ~90 min (LG:42) | re-fit to ~90 min |

### 3.3 Number changes (placeholders for the sims)

- **Garage prices:** Coffee Machine $1,100 → $150, Laptop $4,200 → $800, the first egg $2,300 → $400, Desk 2 $3,600 → $1,000 (economy_sim.py:1068-1073); add Desk 3 $2,500 and a Bug Beetle egg $3,000. The sims raise the Whiteboard and Neon Logo so the Garage keeps ~1.5 h (LONG_K, LG:38; OWNER CHOICE).
- **The free egg is not in the ladder:** `LONG_ITEMS` buys the first hire (economy_sim.py:1071), but OnboardingConfig.lua:20 gives one; that hire takes Desk 1, so the planned Bug Beetle has no desk in the Garage. Add the free egg and Desk 3 to the sim.
- **Garage milestones** at $5K, $20K, $60K and $120K valuation (about 8, 18, 30 and 39 min before the re-fit, estimate): LG 4(b)'s milestones in every rung, giving a title, decor, a task preview, decor. Never Cash (LG:5).

## 4. The first hour (launch, Software)

**Goals, two on the card at a time** (new goal kinds next to `employees` and `stage`, OnboardingServer.lua:136-146; shipped keys `Hire3` and `Seed` kept): 1 "Answer 3 calls" (~2:00), 2 "Own 3 upgrades" (3:34, LG:88), 3 "Hire 3 employees" (12:21), then "Reach milestone 1" (~8:00), "Get a x2 chain" (10 answers in a row, ~20 min), "Buy the Server Rack" (19:04), milestones 2-4 (18:30, 30:09, 39:13), "Reach Seed" (end of session 1). Times: model G2, estimates.

**The first IPO tease** (milestone 1, ~8:00): a dot on IPO; the window opens on "The road to the bell": the seven stages, "Seed: your first funding round", two empty Pokedex frames ("Go public to stamp a company", CUST 1.4). No countdown.

**The gift hook** (TUT 6, ~12:20): the calendar shows Day 2 (10 min of Income) and Day 3's Garage Egg with "Next reward in 19h 40m" (DailyConfig.lua:23-31, 61). Calm text (:53-69).

**Why come back tomorrow:** Day 2-3; the away bank's "saved $X" card (LG:24); a named next target with a time ("Whiteboard · about 12 min"); Seed's round, room and three new tasks shown ahead (BIBLE:271); in Gaming, tomorrow's trending genre (SECT 2.3).

**The first social moment** is visual: poaching is closed (new players are shielded 15 min, CreatureConfig.lua:126; LG R3 proposes 10 engaged hours, LG:108). Neighbors' rooms across the street (WORLD §4), their milestone stars, the in-server board (IpoClient.lua:754). New, optional: a "Cheer" on a neighbor's sign (a clap over their plot, no reward, rate-limited). Planned: the paired demo (ACTIVE §3). The lounge stays paid (ShopConfig.lua:46).

**The first real trade-off** (~11:00): a $3,000 egg (+$5/s on average, sim §5, odds or the next fixed hire shown) or 8 minutes of saving for the Server Rack (+$15/s, certain). Both cards show "pays for itself in about N min". The big one ends session 1: Seed's round, Raise, Later or Skip (FUND 1), never forced.

| Session | Leaves the player with |
|---|---|
| 5 min | Desk, 2 upgrades, 1 hire, ~8 calls, goal 3 started; the next target named |
| 20 min | 3 hires, the Server Rack, milestones 1-2, Day 1 claimed, Day 2 shown, the away bank filling |
| 60 min | 5 upgrades, 4 milestones, an arranged office, the Seed bar about two-thirds full (estimate after the re-fit): a reason to return today |

## 5. Game feel

Every effect is client-only and changes no data (CLAUDE.md, client visuals). "Phone-safe" = no camera shake, no full-white flash, works with sound off.

| Action | Today | Visual | Sound (optional) | Phone-safe |
|---|---|---|---|---|
| Buy | prop pops in, toast (TycoonCore.lua:285; ShopClient.lua:507) | icon pops 1.08x, "+$2/s" floats from the card, 8 sparkles at the prop | register | pop and float |
| Hatch | wobble, flash, card (EmployeeClient.lua:866-940) | flash at 50%, rarity-colored burst | shell crack | no burst |
| Hire | appears at its spot | walks from the incubator to its desk, TEAM count pops | soft ding | same |
| Call answered | toast "+$7" (TaskServer.lua:453-457) | chip flies to the Cash line, "+$7" there, chain grows | pick-up click | float only |
| Call missed | nothing (A11) | chip shakes twice, fades "Missed"; "Chain reset" in gray | none | same |
| Income tick | nothing (A18) | Cash counts up; every 5 s one "+$X" over the top earner on screen | none | count-up only |
| Milestone, stage-up | room flash (TycoonCore.lua:182-186) | card 2.5 s "Seed! New: ..."; the sign spins once; 20 confetti | short fanfare | card |
| IPO | banner 4 s (IpoClient.lua:932-939) | the bell swings, the Pokedex card flips in with its stamp (CUST 1.4) | bell | card |
| Round raised | none yet | a cheque slides in "Raised $X for Y%", the stake ring shrinks | pen and coins | cheque |
| Poach win | result card (PoachClient.lua:1145) | the hire walks in from the street | deal sting | card |
| Poach loss | card, Counter-Offer (:1183-1194) | the hire waves and walks out; a shield bubble over the plot | soft low note | no red flashing |
| Daily claim | toast "Day 1: +$300" (DailyServer.lua:129-142) | the tile flips, Cash counts up, tomorrow's tile glows | gift unwrap | same |

**Sound.** Every sound is an audio asset: uploaded by the owner (it goes through Roblox moderation and counts against an upload allowance) or taken from the Creator Store. Plan: a `SoundConfig` (ReplicatedStorage) with one row per event and `id = 0` until the owner picks a sound, like ShopConfig's IDs; only Roblox-made sounds whose Creator Store page allows use in any experience; volume 0.5; one sound per event at a time; a "Sounds" toggle. **Default: silent**, every event already has its visual. Not verified: the library's license terms, upload limits and fees, which assets the 2022 audio privacy rules still let any experience play.

**Employees.** Today they stroll within 3 studs of their `Home` point every 2-6 s, every frame, within 160 studs (EmployeeClient.lua:978-1002; FR-16). Proposed states: *Work* (a typing bob at the desk), *Stroll* (today's), *React* (a 0.4 s hop when a call is answered, an item pops or a teammate joins; once per 5 s each), *Rest* ("Zz" while quiet mode is on: the office waits for the founder). Coffee Capybara takes breaks at the Coffee Machine.

**Budgets (placeholders):** walkers at 20 Hz, within 80 studs, on screen only (FR-16's fix); at most 6 floating texts and one particle burst (30 particles) at a time; tweens 0.6 s or less; no particles at low graphics quality (unverified API).

## 6. Monetization that feels fair (D9)

**Rules.** No Robux surface in the first 3 minutes, and none the player didn't open: Robux items live in SHOP and appear in context below, never as pop-ups, timers, badges, during a loss (FR-14) or on a touch (A17). **The first Robux prompt** is the player's own tap on a price in SHOP (OWNER CHOICE: no "starter offer").

| Item (ShopConfig.lua) | Shown in context | Promise | Risk |
|---|---|---|---|
| 2x Cash, 199 (:35-42) | Passes tab | double Cash | runs ~6% shorter (CUST 1.5); valuation must stay base (LG:93), so "forever" copy needs care |
| VIP, 249 (:44-51) | a "See VIP" button at the lounge | +50% Cash, tag, lounge | the lounge is a glass box with two seats (ShopServer.lua:626-680) |
| Extra Employee Slots, 149 (:53-61) | the "team full" card | +3 hires | at launch desks cap hires (LG:60): define it as +3 desks, worth up to +15% |
| Auto-Hatch, 199 (:63-71) | Eggs tab after ~10 hatches | no clicking | Income x0.99 (sim §3); online only (EmployeeServer.lua:813-832): say "comfort" |
| Headhunter, 149 (:73-80) | when poaching opens | "+10% success chance" | sells a better chance at a random PvP result, and is sold to restricted players (not `changesOdds`, :193-196): review (question 4) |
| Shareholder, 199 (:82-89) | IPO window near IPO-ready | 2x Shares | perks sooner (~6%, CUST 1.5) |
| Pile / Bag / Vault of Cash, 29 / 99 / 299 (:94-123) | Cash tab only | 10 / 45 / 180 min of Income | today they raise valuation (ShopServer.lua:540): paid IPO speed; launch: gifts (LG:93) |
| Luck Boost, 49 (:124-136) | beside a Startup or Unicorn egg | exact odds before buying (`luckText`) | the only odds copy (SHOP_UX 3.8); hidden when restricted |
| Instant Hatch, 25 (:137-147) | an incubator with 5+ min left | skip one timer | low: the roll is the same (D9_POLICY_OPTIONS.md:20) |
| Poach Shield, 49 (:148-157) | Defense tab, the card after a loss | 1 h of protection | fear selling if timed (FR-14) |

**A free player can always** reach every stage, IPO and sector, hatch every creature (restricted players by the fixed order, EmployeeServer.lua:258-266), earn every stamp tier (targets shrink only by pass share, CUST 1.5) and claim every daily reward (DailyConfig.lua:6).

**The leaderboard.** Today's board ranks IPO count, then best valuation (IpoClient.lua:754), and Cash packs raise valuation: bought speed. At launch it ranks Collection, stamps plus IPOs (CUST 1.6), and valuation counts base Cash only (LG:93): passes buy a little speed, never a higher ceiling.

**Never sold:** valuation, stage or rung skips, engaged time, stamps, tiers, eggs or creatures, random boxes, Gaming's work, quality or wishlists (SECT 2.8); bundles have fixed contents (LG:95).

## 7. Frustration and safety nets

| Situation | Today | Proposal |
|---|---|---|
| Quiet mode | 3 misses or 90 s: "📞 Tap to resume" (TaskConfig.lua:92, 125); a window never counts (TaskServer.lua:232) | the chip says "Calls paused"; employees rest (section 5); no blame |
| Offline | 50% for 8 h (+2 h per Night Shift level, IpoConfig.lua:94), silent (A12); launch: 10% for 2 h (LG:24) | a welcome-back card with the amount and the cap; no Robux on it (M6b's "2x offline" product, ROADMAP.md:90, would sell at that moment) |
| Rejoin | the save reloads, eggs kept hatching (EmployeeServer.lua:640), the task budget refills (PUBLISH_RULES.md:59-61) | the tutorial resumes at its step (TUT §4) |
| Losing an employee | 10 min shield, a 5-min Counter-Offer at 50%, one loss per 10 min, Legendaries safe (CreatureConfig.lua:114-125) | the card adds a free path ("Hatch a new hire") and no Robux (FR-14) |
| A failed save | 3 load tries, then a kick saying progress is safe (TycoonCore.lua:79-80, 746-751); a message after 2 failed saves (:457-472) | keep; a small cloud icon on the bar while saves fail |
| Alone in a server | "Nobody else is in this server yet" (PoachClient.lua:506) | everything else works alone; the Poach tab says when poaching opens; no computer rival that gives employees (it would bypass R2, LG:108); Max Players 6 (PUBLISH_RULES.md:5-11) |
| Low-end phone | rooms up to 260 parts (PLOT_VISUALS.md:34), FR-16, FR-17; the plot streams in after the teleport (WORLD §3) | section 5's budgets, FR-16 and FR-17 fixes, stream the plot in before the teleport (unverified) |
| A very young player | no text input (FULL_REVIEW.md:517) | words a 10-year-old reads (BIBLE:7), calm texts like DailyConfig's (:53), no timed Robux, no "chance" in new copy (D9) |
