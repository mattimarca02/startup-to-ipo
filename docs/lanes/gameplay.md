# Lane: gameplay

Only the gameplay lane edits this file. See docs/LANES.md.

## Backlog (in order)

This list follows docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md section 10, ordered by how much each item helps the first hour. It leaves out the items that belong to other lanes: item 1 (Cash on the bar, IpoClient), item 3 (the Office ladder, ShopClient) and the client halves of item 6.

1. **Goal chain** (build item 7), branch `gameplay-goal-chain`. **Built and pushed, no PR yet** (one PR at a time). It opens as soon as PR #38 is merged. What it does:
   - OnboardingServer checks five new goal kinds: `upgrades`, `owns`, `calls`, `chain` and `ipos`.
   - The server marks which goals the tracker shows, with `OnboardingGoalShown_<key>`, `ShowAtOnce` = 2 at a time. A goal that was showing when it finished stays for 3 s so its tick is seen.
   - OnboardingConfig gets a `Chain` list: Answer 3 calls, Own 3 upgrades, Hire 3, Answer 10 calls in a row, Buy the Server Rack, Seed, Series A, and Go public.
   - The chain sits behind `ChainEnabled = false`, so today's tracker stays exactly as it is.
   - The call goals are skipped while calls are Studio-only.
   - No save change: finished keys go into the existing `onboarding.goals` list, which already keeps keys it doesn't know.
   - New `tools/onboarding_test.py`: 61 checks pass, and the test breaks the code on purpose 10 ways and catches all 10. All the other suites pass.
   - Turning `ChainEnabled` on needs the ux request below; that is a one-line config PR afterwards.
2. **Small first-hour fixes in my files** (part of build item 12):
   - The free-egg toast after `data.ready` (M5 F7).
   - Warnings for bad onboarding values (M5 F9).
   - `OnboardingConfig.Enabled = false` treated as legacy (M5 F4).
   - The Day 1 gift at the first pause, in DailyServer (the DailyClient half goes to ux).
3. **Calls pause under the hatch reveal** (A15). This is mostly EmployeeClient (`OpenPanel`), so it's a request to ux. On the server, TaskServer already freezes calls while a window is open.
4. **Economy core: calls live, the away bank** (build item 8, LONG_GAME PR 2). **Needs the owner:** it changes saved data (the away bank and the 3 h engaged cap) and the economy numbers players have. I'll write the plan here before building anything.
5. **D1 prices, Desk 3, E1 levels I and II, the Garage re-fit** (build item 9). **Needs the owner:** these are economy numbers players already have, and they depend on item 4. The new upgrade names also need the interiors lane (the six-station prop list).
6. **D2 milestones and titles** (build item 10), after item 4. The milestone goals then join the chain.
7. **Welcome-back card** (build item 11). The server part is mine; the offline payout is inside the byte-pinned CLAIMLOAD block, so it needs a careful plan. The card itself is ux's.
8. **Headhunter E2** (build item 13) and **D6 poach prices** (build item 14). **Needs the owner:** a paid item changes and economy numbers move.
9. **Ux R2:** a saved list of the HUD hints a player has seen. **Needs the owner:** it's a new top-level save section (rule A10). Only when ux asks for it.

## Doing now

waiting for the owner: merge PR #38 (quality: MERGE), then the decisions D-A to D-C below for backlog item 4 (economy core)

## Plan for backlog item 4: economy core (LONG_GAME PR 2), waiting for the owner

Not built. It changes saved data and the Cash/valuation numbers players already have, so it waits for a written OK. What is already decided (LONG_GAME section 9, closed): valuation at base Cash (no 2x Cash pass), engaged = a graded task answer in the last 180 s, 3 engaged hours a day at 100% then 5%, Cash packs and daily Cash never count.

What the PR would do, in one branch `gameplay-economy-core` (may split in two: 2a the earnings path, 2b IpoConfig numbers):

1. `IpoServer.addEarnings(player, amount, kind)`, the one choke point, gets a `kind` (`engaged`, `away`, `task`, `debug`); `TycoonCore.addEarnings` forwards it. Valuation counts base Cash only, with the 3 h/day weight from `tasks.engagedDay` / `tasks.engagedSeconds` (already saved since PR 1, so no new field for the cap).
2. The income loop pays Cash every second as today, but only engaged seconds raise the valuation. Away (online or offline, not engaged): the startup banks 10% of base Income for up to 2 h (Night Shift: +30 min a level, 4 h max); the next graded answer pays the bank, 10% of it counts toward valuation.
3. ShopServer's Cash packs stop calling `addEarnings` (a gift, like daily Cash). `TaskConfig.StudioOnly` goes off: calls go live.
4. IpoConfig: Shares 20 / 0.25 / cap 1.5, perk costs from the sim, Night Shift 1,800 s a level, 7 stages (`SeriesCD`, `PreIpo`), `StageScale(L)`. DailyConfig Day 7 drops its 3 Shares. About 28 of the 73 D1 checks in daily_test are rewritten.

Decisions I need from the owner:

- **D-A, gate G1 first?** ROADMAP says G1 (5 players x 2 Studio sessions, calls only, measured f near Garage 0.32 / Seed 0.37 / Series A 0.41) comes before PR 2, and it hasn't been run. My default: run G1 first; I build nothing of item 4 until its numbers are in ROADMAP (or the owner writes "skip G1").
- **D-B, where the away bank is saved.** (a) the proposal's new top-level section `away = { engagedDay, engagedSeconds, bankSeconds }` (rule A10, KNOWN_SECTIONS, Shut down all servers), or (b) one new field `bankSeconds` in the existing `tasks` section. (b) is safe here only because TaskServer already writes back unknown `tasks` fields and `tasks` already holds `engagedDay`/`engagedSeconds`; code older than PR 1 keeps `tasks` whole. My recommendation: (b), one place for the engaged clock, no new section. Either way it is a save-format change and needs your written OK.
- **D-C, the offline payout.** Today: 50% of Income for up to 8 h, paid on join (TycoonCore, inside the byte-pinned CLAIMLOAD block). The plan replaces it with the 10% / 2 h bank. That cuts what a returning player gets by about 20x, and the CLAIMLOAD block's pin in tools/lobby_test.py must move (gameplay's own file). OK to change the offline rule, and in the same PR as the welcome-back card (backlog item 7) so the player sees why?

## Last PR

#38 `gameplay-lobby-test-history` (ux request R1), open.

## Last report (2026-10-17)

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

## Run of 2026-10-17 21:48 UTC (scheduled, no extra text from the manager)

- No requests to the gameplay lane in any lane file or in docs/lanes/owner.md (the owner's "push after every step" rule is followed; the crane cinematic is building's).
- PR #38 (head 094476a) has quality's verdict MERGE and still merges cleanly with main (only lane files changed there). `gameplay-goal-chain` (88252e7) also merges cleanly with main. Nothing rebuilt, no suite re-run (no code changed).
- One PR at a time, so I built nothing new. Item 2 touches OnboardingServer, the same file as the goal chain, so it waits for the goal chain's PR. Instead I wrote the plan for item 4 above, which needs the owner's decisions D-A to D-C.
- This run could not push to `main`: the session's permission check refused it, so this lane file update may only be on branch `gameplay-lane-file` (see the final report).

## Run of 2026-10-17 21:51 UTC (manager fire: "Rebase PR #38 on the latest main, re-run all suites, push, stop")

- Rebased #38 on main 1abde95 (clean; main had only lane files and CONTRIBUTING.md). New head 302491b (was 094476a), force-pushed with lease; `tools/lobby_test.py` is unchanged by the rebase.
- Suites on 302491b, one at a time, Luau 0.742: lobby 155 checks (63/63 mutants), daily 2,813 (282/282), hud 1,073, world 366 (93/93), icon 371 (68/68), shop_ux 6,306 (103/103), building 1,278 (40/40). All green.
- No Studio steps. Still waiting for the owner to merge #38.

## Requests to other lanes

- **U1, to ux (OnboardingClient, for the goal chain):**
  - Draw only the goals the server marks with the player attribute `OnboardingGoalShown_<key> == true`, in the order of `OnboardingConfig.activeGoals()` (use that function, not `OnboardingConfig.Goals`).
  - Size the card for `math.min(OnboardingConfig.ShowAtOnce, #activeGoals())` rows (2), so the card stays 30 + 22 x 2 + 8 high whatever the list's length. Then the tray tests can count rows that way: `onboarding_goal_count` in tools/daily_test.py and tools/hud_test.py.
  - Refresh already fires on attribute names starting with "OnboardingGoal", so the new attribute is covered.
  - Once that is merged, I turn `ChainEnabled` on in a one-line PR.
- **To quality:** after #38 merges, nothing for Studio.

## Studio steps (merged PRs not yet in Studio)

none
