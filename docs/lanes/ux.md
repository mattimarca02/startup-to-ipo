# Lane: ux

Only the ux lane edits this file. See docs/LANES.md.

## Backlog (in order)

1. **DONE (PR #35, merged 2026-10-17 22:25 UTC).** **"Claim garage" button on phones** (branch `ux-claim-button`). A new display-only LocalScript `ClaimButtonClient`: while the server's "Claim garage" prompt is shown on a phone (touch input) and the player has no garage, a big button (at least 240 x 60) sits at the bottom center, above the pop-ups. Tapping it presses the prompt itself (`InputHoldBegin`, then `InputHoldEnd` after the hold time), so the server checks everything as it does today (distance, rate, the garage's state): no new remote, no server change. It hides while a window is open (`OpenPanel`) and with the claim off (`LobbyConfig.ClaimEnabled`, which ships off: nothing changes for live players until the owner turns it on). New file because `LobbyClient.lua` is hash-pinned by tools/lobby_test.py (request R1 below).
2. **BUILT (branch `ux-goal-chain`, pushed, head e665149; PR after item 5's).** **U1 from gameplay: the goal chain in the Goals card (OnboardingClient).** Draw only the goals with the player attribute `OnboardingGoalShown_<key> == true`, in the order of `OnboardingConfig.activeGoals()`, and size the card for `math.min(OnboardingConfig.ShowAtOnce, #activeGoals())` rows, then count rows the same way in tools/hud_test.py's `onboarding_goal_count`. Next after PR #35 (it blocks gameplay turning `ChainEnabled` on). `activeGoals` and `ShowAtOnce` are on main since PR #43. Item 4's X fix goes in the same file, so it waits until this one is done.
3. **IN REVIEW (PR #44, `ux-claim-prompts`).** **Quality follow-ups on ClaimButtonClient and hud_test (not blocking #35).** (a) Keep a set of the claim prompts shown for touch and label the button with the nearest one, so when two show at once and the newer one hides first, the button doesn't disappear while the other is still shown. (b) The HUD mutant "event not disconnected" needs about 3 GB of memory and crashes when several suites run in parallel: cap its loop or shrink the fake. Small, one PR.
4. **Tap targets at least 40 x 40 everywhere.** The Goals tracker's X (OnboardingClient, 30 x 26 today) gets a 44 x 44 hit area without moving the card; a static check in tools/hud_test.py that every TextButton/ImageButton with a fixed size in the clients is at least 40 px on each side.
5. **BUILT, PR after #44 (branch `ux-sync-history`, pushed).** **Unpin my tests' Studio-sync hashes.** tools/hud_test.py (IpoClient in docs/STUDIO_SYNC_HUD.md) and tools/shop_ux_test.py (ShopClient and ShopLayout in docs/STUDIO_SYNC_SHOP.md) compare those docs with today's files, so any later edit of IpoClient or ShopClient fails them. Check them against the files at the commit the doc was written for (like lobby_test's L1 section), so the docs stay history. Needed before items 6 to 8 (which touch IpoClient and ShopClient); also needs R1.
6. **One place for pop-ups.** Seven toasts sit at seven heights today (Shop, IPO and Task at -16, Employee -72, Poach -128, Onboarding -184, Daily -240) with different sizes and fonts. Give them one style (size, font, colour, time) and a fixed stack so two never cover each other, on both phone sizes.
7. **Clearer HUD buttons.** EGGS, SHOP, TEAM, POACH, IPO: the same size, icon plus a short label that fits at 64 x 64 (short screens) and 76 x 76, one badge style for "something is waiting".
8. **A first-time hint for each HUD button.** A one-time pulse and a short line ("Hire your first employee here") the first time a button matters. Showing it only once across sessions needs saved data: request to gameplay (R2) before building; a session-only version can come first.

## Doing now

waiting for the owner: item 5 (`ux-sync-history`) and item 2 (`ux-goal-chain`) are built and pushed, each to become a PR one at a time; nothing open now. #44 is merged.

## Last PR

PR #44 (`ux-claim-prompts`), merged 2026-10-18 08:53 UTC: https://github.com/mattimarca02/startup-to-ipo/pull/44. Before it: PR #35, merged 2026-10-17.

## Last report

2026-10-18, two runs. (1) 08:05 to 09:20 UTC: gameplay's PR #43 is merged, so I built backlog item 2 (U1) on `ux-goal-chain`. The Goals card (OnboardingClient) reads `OnboardingConfig.activeGoals()`, has `math.min(ShowAtOnce, #goals)` rows (82 px high even with the 8-goal chain) and fills them in list order with the goals the server marks `OnboardingGoalShown_<key> == true`; an empty row stays empty; with an older server that marks none it draws the first goals as before; a goal the server can't check (the call goals outside Studio) no longer blocks "All goals done!". Display only, nothing changes for players while `ChainEnabled` is off. hud_test and daily_test count the card's rows the same way, and hud_test runs the real client in a fake (new tools/onboarding_client_test.luau: 27 checks + 3 static, 9 of 9 mutants, self-test OK; 6 of its checks fail on main's old client). The branch has main merged in (e665149) and carries no claim rows. Suites, one at a time: hud 1073 (69/69, coupling 26/26) + claim button 129 (28/28) + Goals card above, daily all green, world 380 (101/101), icon 371 (68/68), shop_ux 6306 (103/103), lobby 155 (63/63), building 1407 (46/46), onboarding 61 (10/10). No PR yet: another ux session started item 5 at 08:55, and the lane keeps one PR at a time. (2) A manager fire asked to rebase PR #44 on main: nothing to do, the owner merged #44 at 08:53 UTC. The claim rows for OnboardingClient, daily_test (checks of ux) and tools/onboarding_client_test.luau are not on main yet: my pushes to main were refused in the first run.

2026-10-17, scheduled run. Backlog item 2 (U1, the goal chain in the Goals card) still waits: `OnboardingConfig.activeGoals` is only on PR #43, which isn't merged. So I built item 3 as PR #44: https://github.com/mattimarca02/startup-to-ipo/pull/44.

What changed: ClaimButtonClient now keeps a list of every claim prompt shown for touch. The button names and presses the nearest one (the newest when there is no character yet or two are equally near). It looks again twice a second while two or more show, and it drops a prompt that has left its post. So the newer prompt hiding first no longer hides the button while another is still shown. It is still display only: no remote, no server change, nothing with the claim off. In tools/hud_test.py, the "events" scenario stops its add/remove loop once listeners pile up. The "event not disconnected" mutant is now caught in about 2 s instead of 37 s and about 3 GB of memory.

Tests (Luau 0.742, one at a time, with main 9105aea merged in): hud 1073 checks and 69/69 mutants, plus the claim button's 129 checks and 28/28 mutants (12 new checks, 7 new mutants). daily 2822 (281/281), world 380 (101/101), icon 371 (68/68), shop_ux 6306 (103/103), lobby 155 (63/63), building 1407 (46/46). All green.

Not done this run: pushing my claim rows and this lane file straight to main was refused by the run's permission check. Both are on the PR branch instead (CONTRIBUTING.md claim rows for ClaimButtonClient, tools/claim_button_test.luau, tools/hud_test.py). Owner: if lane-file pushes to main should work in scheduled runs, that permission needs allowing; until then this file reaches main with the PR. Requests: none new. Waiting for the owner: the review and merge of PR #44.

Later run, 2026-10-17 (a manager fire: "continue with the next item of your backlog"). PR #44 has no review yet and is still open, and a lane keeps one PR at a time, so I built the next item on a branch without opening a PR, as the gameplay lane did with the goal chain. Item 2 still waits for `OnboardingConfig.activeGoals` (PR #43, not merged). Item 4 needs OnboardingClient, which item 2 changes first. So I built item 5 on `ux-sync-history`.

What it does: docs/STUDIO_SYNC_HUD.md and docs/STUDIO_SYNC_SHOP.md were last brought up to date at `645393a` (lobby L3), and new Studio steps go to docs/STUDIO_SYNC_BATCH.md. So tools/hud_test.py and tools/shop_ux_test.py now check those docs against IpoClient, ShopClient and ShopLayout as they were at that commit (`SYNC_COMMIT`, read with git show), like lobby_test does. A missing git history fails a named check. I checked it three ways. A comment added to IpoClient, ShopClient and ShopLayout keeps every suite green (on main the same edit fails 2 hud checks). A changed hash in either doc still fails its named check. And the branch merges cleanly with #44. Suites on the branch: hud 1073 (69/69, coupling 26/26), daily 2822 (281/281), world 380 (101/101), icon 371 (68/68), shop_ux 6308 (103/103; +2 named "can be read" checks), lobby 155 (63/63), building 1407 (46/46). No Studio steps (test files only). Its claim row for tools/shop_ux_test.py is on that branch, because pushes to main are still refused in these runs.

## Requests to other lanes

- **To gameplay (U1): built** on `ux-goal-chain`; once it is merged, `ChainEnabled` can go on in your one-line PR.
- **To quality:** once `ux-goal-chain` is merged: README's tools row for tools/onboarding_client_test.luau (run by tools/hud_test.py) and the Studio step above in the batch.
- **R1, to gameplay (tools/lobby_test.py): DONE (PR #38, merged).** its "Lobby all" doc checks (`ALL_SCRIPTS`) compare docs/STUDIO_SYNC_LOBBY.md with today's bytes of ShopClient, IpoClient, LobbyClient, EmployeeClient, BuildingClient (and TycoonCore, ShopServer, WorldArt, WorldVisuals, PlotVisuals, ...). That doc is history now (lobby-all is merged; new Studio steps go to docs/STUDIO_SYNC_BATCH.md), so any later edit of one of those files fails lobby_test, in every lane. Please check that section against the files at the lobby-all merge commit `2df1410`, the way the L1 section uses `L1_COMMIT = "f6a546f"`. 
- **R2, to gameplay (later, item 6):** a place to save which HUD hints a player has seen (a list of short keys). Rule A10 says a new top-level section; it needs the owner's written OK. Not needed yet (item 8).
- **To quality:** when PR `ux-claim-button` is merged, README.md and CLAUDE.md need the new LocalScript `ClaimButtonClient` (StarterPlayer > StarterPlayerScripts, display only, no remote; it presses the server's own claim prompt) and its Studio step goes in the batch.

## Studio steps (merged PRs not yet in Studio)

`ux-goal-chain` (item 2), once it is merged: paste OnboardingClient.lua into the LocalScript `OnboardingClient` (StarterPlayer > StarterPlayerScripts): sha256 `7c69d99f8c2c02667100c0538b238250e7f6a71c0713cdb090dfc7862cdffdb5`, 14691 bytes. F5 as a new player: once the free egg hatches the card shows "Hire 3 employees" and "Reach Seed stage" as before, no errors in Output.

PR #44, once it is merged: paste ClaimButtonClient.lua into the LocalScript `ClaimButtonClient` (sha256 `b00fcd8637d378eca02d3e6b4b856ee9fea8d184ea3086a2031d0eee124817c4`, 10261 bytes; it replaces PR #35's version), then steps 3 and 4 below.

PR #35, once it is merged:
1. Create a LocalScript named exactly `ClaimButtonClient` in StarterPlayer > StarterPlayerScripts.
2. Paste ClaimButtonClient.lua into it (sha256 `494d14bdd2843e49606a7a339793e9b4c7840ea0cc08f967f5f7c3863bed2b00`, 7525 bytes).
3. Press F5 with the claim off: nothing new shows and the Output window has no errors.
4. Optional, never published: set ClaimEnabled to true, then use Test > Device with a phone in portrait and landscape, walk to a free garage and tap the button. Set ClaimEnabled back to false afterwards.
