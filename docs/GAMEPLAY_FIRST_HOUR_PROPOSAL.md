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
