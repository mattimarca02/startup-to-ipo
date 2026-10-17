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

waiting for review of PR #38

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
- **Waiting for the owner:** nothing yet. Backlog items 4, 5, 8 and 9 will each need a written decision before I build them.
- Claims still held: OnboardingServer, OnboardingConfig and tools/onboarding_test.py (for gameplay-goal-chain), and tools/lobby_test.py (for #38).

## Requests to other lanes

- **U1, to ux (OnboardingClient, for the goal chain):**
  - Draw only the goals the server marks with the player attribute `OnboardingGoalShown_<key> == true`, in the order of `OnboardingConfig.activeGoals()` (use that function, not `OnboardingConfig.Goals`).
  - Size the card for `math.min(OnboardingConfig.ShowAtOnce, #activeGoals())` rows (2), so the card stays 30 + 22 x 2 + 8 high whatever the list's length. Then the tray tests can count rows that way: `onboarding_goal_count` in tools/daily_test.py and tools/hud_test.py.
  - Refresh already fires on attribute names starting with "OnboardingGoal", so the new attribute is covered.
  - Once that is merged, I turn `ChainEnabled` on in a one-line PR.
- **To quality:** after #38 merges, nothing for Studio.

## Studio steps (merged PRs not yet in Studio)

none
