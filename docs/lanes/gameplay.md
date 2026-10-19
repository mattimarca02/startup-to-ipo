# Lane: gameplay

Only the gameplay lane edits this file. See docs/LANES.md.

## Backlog (in order)

This list follows docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md section 10, ordered by how much each item helps the first hour. It leaves out the items that belong to other lanes: item 1 (Cash on the bar, IpoClient), item 3 (the Office ladder, ShopClient) and the client halves of item 6.

1. **Goal chain** (build item 7), branch `gameplay-goal-chain`, **PR #43, merged 2026-10-18.** What it does:
   - OnboardingServer checks five new goal kinds: `upgrades`, `owns`, `calls`, `chain` and `ipos`.
   - The server marks which goals the tracker shows, with `OnboardingGoalShown_<key>`, `ShowAtOnce` = 2 at a time. A goal that was showing when it finished stays for 3 s so its tick is seen.
   - OnboardingConfig gets a `Chain` list: Answer 3 calls, Own 3 upgrades, Hire 3, Answer 10 calls in a row, Buy the Server Rack, Seed, Series A, and Go public.
   - The chain sits behind `ChainEnabled = false`, so today's tracker stays exactly as it is.
   - The call goals are skipped while calls are Studio-only.
   - No save change: finished keys go into the existing `onboarding.goals` list, which already keeps keys it doesn't know.
   - New `tools/onboarding_test.py`: 61 checks pass, and the test breaks the code on purpose 10 ways and catches all 10. All the other suites pass.
   - Turning `ChainEnabled` on needs the ux request below; that is a one-line config PR afterwards.
2. **Small first-hour fixes in my files** (part of build item 12). **PR #51 (merged): F7, F9, F4 and M6 F2, F4. PR #52 (merged): the Day 1 gift at the first pause, server and config only (no client change needed).**
   - The free-egg toast after `data.ready` (M5 F7).
   - Warnings for bad onboarding values (M5 F9).
   - `OnboardingConfig.Enabled = false` treated as legacy (M5 F4).
   - The Day 1 gift at the first pause, in DailyServer (the DailyClient half goes to ux).
3. **Calls pause under the hatch reveal** (A15). This is mostly EmployeeClient (`OpenPanel`), so it's request U2 to ux (below). On the server, TaskServer already freezes calls while a window is open. (Overhaul note: `ChainEnabled` is on since phase 4, so item 1 is fully done.)
4. **Economy core: calls live, the away bank** (build item 8, LONG_GAME PR 2). **Needs the owner:** it changes saved data (the away bank and the 3 h engaged cap) and the economy numbers players have. I'll write the plan here before building anything.
5. **D1 prices, Desk 3, E1 levels I and II, the Garage re-fit** (build item 9). **Needs the owner:** these are economy numbers players already have, and they depend on item 4. The new upgrade names also need the interiors lane (the six-station prop list).
6. **D2 milestones and titles** (build item 10), after item 4. The milestone goals then join the chain.
7. **Welcome-back message** (build item 11), branch `gameplay-welcome-back`, **PR #61, merged 2026-10-19.** A server pop-up through `ShopServer.notify`; the offline pay and the CLAIMLOAD block are unchanged. If ux wants a full card later, I can add display-only player attributes (Cash, seconds away, capped).
8. **Headhunter E2** (build item 13) and **D6 poach prices** (build item 14). **Needs the owner:** a paid item changes and economy numbers move.
9. **Ux R2:** a saved list of the HUD hints a player has seen. **Needs the owner:** it's a new top-level save section (rule A10). Only when ux asks for it.

## Plan for backlog item 4: economy core (LONG_GAME PR 2), waiting for the owner

Not built. It changes saved data and the Cash/valuation numbers players already have, so it waits for a written OK. What is already decided (LONG_GAME section 9, closed): valuation at base Cash (no 2x Cash pass), engaged = a graded task answer in the last 180 s, 3 engaged hours a day at 100% then 5%, Cash packs and daily Cash never count.

What the PR would do, in one branch `gameplay-economy-core` (may split in two: 2a the earnings path, 2b IpoConfig numbers):

1. `IpoServer.addEarnings(player, amount, kind)`, the one choke point, gets a `kind` (`engaged`, `away`, `task`, `debug`); `TycoonCore.addEarnings` forwards it. Valuation counts base Cash only, with the 3 h/day weight from `tasks.engagedDay` / `tasks.engagedSeconds` (already saved since PR 1, so no new field for the cap).
2. The income loop pays Cash every second as today, but only engaged seconds raise the valuation. Away (online or offline, not engaged): the startup banks 10% of base Income for up to 2 h (Night Shift: +30 min a level, 4 h max); the next graded answer pays the bank, 10% of it counts toward valuation.
3. ShopServer's Cash packs stop calling `addEarnings` (a gift, like daily Cash). `TaskConfig.StudioOnly` goes off: calls go live.
4. IpoConfig: Shares 20 / 0.25 / cap 1.5, perk costs from the sim, Night Shift 1,800 s a level, 7 stages (`SeriesCD`, `PreIpo`), `StageScale(L)`. DailyConfig Day 7 drops its 3 Shares. About 28 of the 73 D1 checks in daily_test are rewritten.

The owner's answers (owner.md, 2026-10-18), and what they change in the plan:

- **D-A: G1 first.** I build nothing of item 4 until G1's numbers are in ROADMAP (or the owner writes "skip G1"). G1 is still not run (ROADMAP M6 "Next").
- **D-B: a new top-level section** `away = { engagedDay, engagedSeconds, bankSeconds }` (rule A10: its own serialize, an entry in KNOWN_SECTIONS, optional on load, Shut down all servers when published). `tasks.engagedDay` / `engagedSeconds` stay where they are and keep being written, so an older server (or a rollback) still reads them. The new code reads `away` first and falls back to `tasks` when `away` is missing.
- **D-C: the offline Cash stays.** It is still 50% of Income for up to 8 h, paid on join. Only the valuation side changes. Here is the variant, written as the owner asked:
  - **Recommended: 10% of the offline Cash counts toward the valuation.** That is the same share the away bank's payout gets (LG:24), so "away" means one thing whether you are offline or idle online. It is also a real but small part of the IPO pace: a full 8 h night pays 4 Income-hours of Cash and adds 0.4 Income-hours of valuation, about 30% of one engaged Garage hour (1.32, GAMEPLAY_FIRST_HOUR_PROPOSAL section 2). Today that night adds 4.0, three times an engaged hour, which is the AFK-beats-play problem.
  - **The other option: 0%.** It is the simplest, but then the welcome-back message announces Cash that does nothing for the IPO, and Night Shift (an IPO perk) would only buy Cash.
  - **The CLAIMLOAD block stays byte-identical in both options.** The block already calls `addEarnings(player, earned)` before `data.ready`. Since PR #61, `addEarnings` (outside the block) knows that call is the offline pay: it is the only earnings before `ready`. So the weight goes there: `IpoServer.addEarnings(player, amount, data.ready and kind or "offline")`. Nothing inside the markers moves, and `tools/lobby_test.py` keeps its pin.
  - After G1, if the numbers say more is needed (a lower cap or a lower share), I propose it then, as the owner asked.
- **Still open for the owner when item 4 starts:** pick the share, 10% (my recommendation) or 0%.

## Doing now

idle (PR #61 merged; the next free item needs the owner or gate G1, see the run notes)

## Last PR

#61 `gameplay-welcome-back`, merged 2026-10-19 08:59 UTC. Before it: #52 `gameplay-gift-first-pause`, merged 2026-10-18 11:45 UTC. Before it: #51 `gameplay-first-hour-fixes`, merged 2026-10-18. Before it: #43 `gameplay-goal-chain` (goal chain), merged 2026-10-18 08:19 UTC. Before it: #38 `gameplay-lobby-test-history` (ux R1), merged 2026-10-17.

## Note (2026-10-19 09:00 UTC)

- **PR #61 is merged.** I released my claims on TycoonCore, tools/lobby_test.py and tools/lobby_runtime.luau.
- **For quality's batch:** its Studio step is the TycoonCore row under "Studio steps" below.
- **Waiting for the owner:**
  - Gate G1 (items 4 and 6).
  - The offline valuation share, 10% or 0% (item 4).
  - Written OKs for items 5 and 8.
- **Waiting on the ux lane:** request U2 (item 3).

## Run (2026-10-18, manual fire: "continue with the next item of your backlog")

- **No new PR.** PR #61 is still open with no review, and a lane keeps one PR at a time (docs/LANES.md rule 3). Every other item is blocked:
  - Item 3 is ux's (request U2).
  - Items 4 and 6 wait for gate G1.
  - Items 5 and 8 change economy numbers or a paid item, so they need the owner.
  - Item 9 waits until ux asks for it.
- **What I did instead:** I wrote the D-C variant the owner asked for into the item 4 plan above. The offline Cash stays as it is, and I recommend that 10% of it counts toward the valuation (0% is the other option). The CLAIMLOAD block stays byte-identical, because the weight goes into `addEarnings` outside the block.
- **Tests:** none run this time (docs only). **Studio steps:** none new.
- **Waiting for the owner:**
  - Review and merge of PR #61.
  - Gate G1.
  - The offline valuation share (10% or 0%), when item 4 starts.

## Report (2026-10-18, PR #61 open)

- **Read the overhaul report first.** The goal chain is already on (`ChainEnabled`, phase 4), and calls stay Studio-only. No lane has an open request for me.
- **Built backlog item 7 as PR #61:** https://github.com/mattimarca02/startup-to-ipo/pull/61
  - A player who comes back after 5 minutes or more gets one pop-up about 3 s after loading: "Welcome back! You earned $12.3K while away (3h 12m)", or "(8h max)" if they reached the offline cap.
  - The offline pay is unchanged (the owner's D-C answer). The CLAIMLOAD block is byte-identical. Nothing is saved, and there is no new remote and no client change.
- **Tests:**
  - lobby: 172 checks, 70 of 70 mutants caught. That includes 12 new checks that run the real TycoonCore and 5 new mutants.
  - All other suites pass: daily, onboarding 82 (16/16), hud 1073, world 389, icon 371, shop_ux 6308, building 1423.
- **Studio steps:** the TycoonCore row below, for quality's batch once #61 is merged.
- **Requests made:** U2 to ux (calls pause under the hatch reveal).
- **Waiting for the owner:**
  - Review and merge of #61.
  - Gate G1 for item 4.
- **Claims held:** TycoonCore, tools/lobby_test.py, tools/lobby_runtime.luau.

## Note (2026-10-18 11:45 UTC)

- **PR #52 is merged** (quality: MERGE). I released DailyServer, DailyConfig and the daily checks of daily_test.py. Its two Studio rows below are for quality's next batch. No claims held now.

## Last report (2026-10-18 10:15 UTC, PR #52 open)

- **PR #51 is merged.** I released OnboardingServer and tools/onboarding_test.py. Its Studio rows stay below for quality's batch.
- **Built the rest of backlog item 2 as PR #52:** https://github.com/mattimarca02/startup-to-ipo/pull/52
  - A brand-new player's Day 1 gift now opens by itself at the first pause: 10 s after their third employee (TUT 6, about minute 10). Before, it never opened by itself in session 1.
  - Old players, players who have claimed before and onboarding switched off work as today.
  - DailyConfig: new `FirstPause = { employees = 3, delay = 10 }`, and `AutoOpenWithin` goes from 60 to 1800 s so the window can still open then. No DailyClient change was needed, so no request to ux.
  - No save change, no reward or price change.
- **Tests:** the daily calendar has 115 checks (13 new, driving the server's real every-second loop), and 4 hand-made breaks are each caught by a named check. Every other suite passes: onboarding 78 (16/16), hud, world 380, icon 371, shop_ux 6,308, lobby 155, building 1,407.
- **Studio steps:** PR #52's rows below, once it is merged.
- **Requests made:** none. **Waiting for the owner:** gate G1 for backlog item 4, and the review and merge of PR #52.
- **Claims held** (docs/lanes/claims.md): DailyServer, DailyConfig, daily_test.py (checks of gameplay: daily).

## Report (2026-10-18 10:01 UTC, PR #51 open)

- **The owner answered D-A to D-C** (owner.md): G1 first, the `away` section as a new top-level section, and the offline Cash stays (only part of it may count toward the valuation). So I built nothing of backlog item 4; it waits for G1's numbers in ROADMAP.
- **Built backlog item 2 as PR #51:** https://github.com/mattimarca02/startup-to-ipo/pull/51
  - The free-egg pop-up now waits until the player has finished loading, and is sent once (M5 F7).
  - A save with progress but no free egg on record counts as an old player, also when onboarding was switched off when it was written (M5 F4).
  - Bad values in the saved onboarding section now give a warning instead of being changed silently (M5 F9).
  - Day 7 (the Shares day) is refused before anything is given while an IPO is being filed, so the day is never used up with half its reward (M6 F2).
  - The Studio Debug calendar buttons now say they write the real save (M6 F4).
- **Tests:** onboarding 78 checks, 16 of 16 mutants caught; the daily calendar 102 checks (5 new); every other part of daily_test, and hud, world, icon, shop_ux, lobby and building all pass on main 68f0937.
- **Studio steps:** the two rows below, once it is merged.
- **Requests made:** none. **Waiting for the owner:** gate G1 (for backlog item 4); a merge of PR #51 after quality's review.
- **Claims held** (docs/lanes/claims.md): OnboardingServer, DailyServer, tools/onboarding_test.py, daily_test.py (checks of gameplay: daily).

## Report (2026-10-17)

- **Handled the ux lane's request R1 first.** In `tools/lobby_test.py`, the "Lobby all" sync-doc hash checks now read the scripts as they were at the lobby-all merge (`ALL_COMMIT = 2df1410`, using `git show`), like the L1 section already does. Before this, any edit to TycoonCore, ShopServer, IpoClient, ShopClient and ten more scripts failed lobby_test in every lane. Now it doesn't: I added a comment to IpoClient and ShopServer as a test, and it stayed green.
  - lobby_test: 155 checks pass and it catches 63 of 63 broken versions. I removed one broken version because it no longer applies: it tested that the doc's hash goes stale.
  - Every other suite passes: daily (2,813 checks), hud, world, icon, shop_ux and building.
  - PR: https://github.com/mattimarca02/startup-to-ipo/pull/38. No Studio steps.
- **Built the goal chain** (backlog item 1) on `gameplay-goal-chain`. It's pushed but has no PR yet, because a lane has one PR at a time. Every suite passes on it, plus the new `tools/onboarding_test.py`.
  - Studio steps once it's merged: paste `OnboardingServer` (ServerScriptService) and `OnboardingConfig` (ReplicatedStorage). OnboardingServer now requires `TaskConfig`, which already exists. Nothing changes on screen while `ChainEnabled` is false.
- **Requests made:** U1 to ux (below).

## Later run (2026-10-17, a manual fire: "fill your backlog, then build the first item")

- **No new work.** The backlog was already filled and item 1 built on the first run. A lane keeps one PR open at a time, so I built nothing new.
- **Same request from two more lanes.** The building lane's B1 and the world lane's request 1 ask for the same fix as ux R1, so PR #38 covers them too.
- **Fixed PR #38 after a merge.** PR #34 (kit front 180, checked in Studio) merged after #38 was opened. It updated PlotBuilding's row in the "Lobby all" section, so pinning that section at `2df1410` gave 4 failures. I rebased #38 on main and moved the pin to `fb8c057`, the commit after #34.
  - lobby_test: 155 checks pass, 63 of 63 broken versions caught.
  - daily, hud, world, icon, shop_ux and building all pass.
- **Not done:** the world lane's extra ask, checking a file that changed since then against its lane file's "Studio steps" row. Studio steps now go in quality's batch doc (docs/STUDIO_SYNC_BATCH.md), so that check belongs with the batch, not lobby_test.
- **Waiting for the owner:** nothing yet. Backlog items 4, 5, 8 and 9 will each need a written decision before I build them.
- Claims still held: OnboardingServer, OnboardingConfig and tools/onboarding_test.py (for gameplay-goal-chain), and tools/lobby_test.py (for #38).

## Report (2026-10-17 22:20 UTC, PR #38 merged)

- **PR #38 is merged.** I released the claim on tools/lobby_test.py. No Studio steps (it's a test file).
- **Opened PR #43 for the goal chain:** https://github.com/mattimarca02/startup-to-ipo/pull/43. I rebased it on main 598ae84 and ran every suite one at a time (quality's advice). All pass:
  - onboarding: 61 checks, 10 of 10 mutants caught;
  - lobby: 155 checks, 63 of 63 mutants;
  - building: 1,278 checks, 40 of 40 mutants;
  - daily, hud, world, icon and shop_ux.
- **Nothing changes for players** while `ChainEnabled` is false. Turning it on waits for the ux lane's U1 (item 2 in their backlog).
- **Studio steps after merge (for the batch):** paste the two scripts below and playtest (F5); the tracker should look as before (Hire 3, Seed) and the Output should show no OnboardingConfig warning.
- **Waiting for the owner:** nothing.
- **Claims held:** OnboardingServer, OnboardingConfig and tools/onboarding_test.py.

## Report (2026-10-17 23:20 UTC, safety-net check of PR #43)

- **Quality's verdict on PR #43 is MERGE,** once it's rebased on main. Done:
  - I rebased it on main 9105aea.
  - I fixed quality's nit: a deliberately broken version of the code whose test run errors is no longer counted as caught.
  - I re-ran every suite one at a time. All pass: onboarding 61 (10/10), daily, hud, world 380 (101/101), icon 371, shop_ux 6,306, lobby 155 (63/63), building 1,407 (46/46).
  - The two scripts' hashes are unchanged (only the test file changed).
- **PR #42 is ported and closed,** as quality asked. It was another run's lane file that couldn't be pushed to main. Its plan for item 4 (the economy core) is now the section above.
- **Waiting for the owner: decisions D-A, D-B and D-C** in that section (run gate G1 first; where the away bank is saved; the offline payout). I build nothing of item 4 until you answer in writing.

## Report (2026-10-18 08:25 UTC, PR #43 merged)

- **PR #43 (the goal chain) is merged.** I released the claims on OnboardingServer, OnboardingConfig and tools/onboarding_test.py.
- **For quality's batch:** its Studio steps are the two rows below. Paste the two scripts, playtest with F5, and the tracker should look as before (Hire 3, Seed), with no OnboardingConfig warning in the Output.
- **Waiting on others:**
  - The chain stays off (`ChainEnabled = false`) until the ux lane's U1 is merged; then I turn it on in a one-line PR.
  - Backlog item 4 waits for the owner's decisions D-A, D-B and D-C (above).

## Requests to other lanes

- **U2, to ux (EmployeeClient, A15, backlog item 3):** while the hatch reveal plays, set the PlayerGui attribute `OpenPanel` (for example `"Hatch"`) and clear it when the reveal ends, if no other window took it in the meantime. TaskServer already holds calls while a window is open, so a call no longer rings or runs out behind the reveal. No server change needed.
- **U1, to ux (OnboardingClient, for the goal chain):**
  - Draw only the goals the server marks with the player attribute `OnboardingGoalShown_<key> == true`, in the order of `OnboardingConfig.activeGoals()` (use that function, not `OnboardingConfig.Goals`).
  - Size the card for `math.min(OnboardingConfig.ShowAtOnce, #activeGoals())` rows (2), so the card stays 30 + 22 x 2 + 8 high whatever the list's length. Then the tray tests can count rows that way: `onboarding_goal_count` in tools/daily_test.py and tools/hud_test.py.
  - Refresh already fires on attribute names starting with "OnboardingGoal", so the new attribute is covered.
  - Once that is merged, I turn `ChainEnabled` on in a one-line PR.
- **To quality:** PR #43's Studio steps for the batch, once it's merged: the rows under "Studio steps" below.

## Studio steps (merged PRs not yet in Studio)

PR #61 (merged 2026-10-19; for the batch):

| Script | Studio | State | sha256 | bytes |
|---|---|---|---|---|
| `TycoonCore` | Script, ServerScriptService | changed | `47e00621d8c50a41ecf59cd3dccba7d0fbcd67d1d88337edbe62daa3c1310e84` | 58854 |

Playtest: play with the Desk, stop, wait 5+ minutes, play again: about 3 s after the load the bottom pop-up says "Welcome back! You earned $... while away (..m)".

PR #52 (merged 2026-10-18 11:45 UTC; for the batch):

| Script | Studio | State | sha256 | bytes |
|---|---|---|---|---|
| `DailyServer` | ModuleScript, ServerScriptService | changed | `3527123c3f33bc7f4b43cd89cddd9d9eb08aa3fc026d3a7a99ebad1e308e1ba1` | 17574 |
| `DailyConfig` | ModuleScript, ReplicatedStorage | changed | `9a7a6820182ab984e36a153e983833b991d2f4a90c1d8088dea15d982a1a8693` | 7290 |

Playtest: Debug > Onboarding restart, then Daily reset; hire up to 3 employees; about 10 s later the Daily window opens by itself on Day 1.

PR #51 (merged 2026-10-18; replaced by PR #52's DailyServer row if both go in the same batch):

| Script | Studio | State | sha256 | bytes |
|---|---|---|---|---|
| `OnboardingServer` | ModuleScript, ServerScriptService | changed | `e6ae15bcb7d7b7a6f89ae22102ffab04fb695e31ea548a4e08a7c81bcb58b5af` | 17546 |
| `DailyServer` | ModuleScript, ServerScriptService | changed | `4df0c1d0d0d715a8ed1d9a221dbfa5f65d7654d13efc2bb80a69b2a32a38b517` | 16381 |

Playtest: Debug > Onboarding restart shows the free-egg pop-up about a second later, once.

(PR #43's rows below are already in Batch 1.)

PR #43 (merged 2026-10-18), for docs/STUDIO_SYNC_BATCH.md:

| Script | Studio | State | sha256 | bytes |
|---|---|---|---|---|
| `OnboardingServer` | ModuleScript, ServerScriptService | changed | `a77c805d733252ad7d4c90232092212fe872212686c74b96de6fa22ef9c0b2d7` | 16509 |
| `OnboardingConfig` | ModuleScript, ReplicatedStorage | changed | `7406818ffa279b69487e73334ca1fb5dfe99e343912d1ab10301df753904f7f4` | 6883 |
