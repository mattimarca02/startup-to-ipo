# Lane: ux

Only the ux lane edits this file. See docs/LANES.md.

## Backlog (in order)

1. **DONE (PR #35, merged 2026-10-17 22:25 UTC).** **"Claim garage" button on phones** (branch `ux-claim-button`). A new display-only LocalScript `ClaimButtonClient`: while the server's "Claim garage" prompt is shown on a phone (touch input) and the player has no garage, a big button (at least 240 x 60) sits at the bottom center, above the pop-ups. Tapping it presses the prompt itself (`InputHoldBegin`, then `InputHoldEnd` after the hold time), so the server checks everything as it does today (distance, rate, the garage's state): no new remote, no server change. It hides while a window is open (`OpenPanel`) and with the claim off (`LobbyConfig.ClaimEnabled`, which ships off: nothing changes for live players until the owner turns it on). New file because `LobbyClient.lua` is hash-pinned by tools/lobby_test.py (request R1 below).
2. **IN REVIEW (PR #53, `ux-goal-chain`).** **U1 from gameplay: the goal chain in the Goals card (OnboardingClient).** Draw only the goals with the player attribute `OnboardingGoalShown_<key> == true`, in the order of `OnboardingConfig.activeGoals()`, and size the card for `math.min(OnboardingConfig.ShowAtOnce, #activeGoals())` rows, then count rows the same way in tools/hud_test.py's `onboarding_goal_count`. Next after PR #35 (it blocks gameplay turning `ChainEnabled` on). `activeGoals` and `ShowAtOnce` are on main since PR #43. Item 4's X fix goes in the same file, so it waits until this one is done.
3. **DONE (PR #44, merged 2026-10-18 08:53 UTC).** **Quality follow-ups on ClaimButtonClient and hud_test (not blocking #35).** (a) Keep a set of the claim prompts shown for touch and label the button with the nearest one, so when two show at once and the newer one hides first, the button doesn't disappear while the other is still shown. (b) The HUD mutant "event not disconnected" needs about 3 GB of memory and crashes when several suites run in parallel: cap its loop or shrink the fake. Small, one PR.
4. **Tap targets at least 40 x 40 everywhere.** The Goals tracker's X (OnboardingClient, 30 x 26 today) gets a 44 x 44 hit area without moving the card; a static check in tools/hud_test.py that every TextButton/ImageButton with a fixed size in the clients is at least 40 px on each side.
5. **DONE (PR #48, merged 2026-10-18 09:18 UTC).** **Unpin my tests' Studio-sync hashes.** tools/hud_test.py (IpoClient in docs/STUDIO_SYNC_HUD.md) and tools/shop_ux_test.py (ShopClient and ShopLayout in docs/STUDIO_SYNC_SHOP.md) compare those docs with today's files, so any later edit of IpoClient or ShopClient fails them. Check them against the files at the commit the doc was written for (like lobby_test's L1 section), so the docs stay history. Needed before items 6 to 8 (which touch IpoClient and ShopClient); also needs R1.
6. **One place for pop-ups.** Seven toasts sit at seven heights today (Shop, IPO and Task at -16, Employee -72, Poach -128, Onboarding -184, Daily -240) with different sizes and fonts. Give them one style (size, font, colour, time) and a fixed stack so two never cover each other, on both phone sizes.
7. **Clearer HUD buttons.** EGGS, SHOP, TEAM, POACH, IPO: the same size, icon plus a short label that fits at 64 x 64 (short screens) and 76 x 76, one badge style for "something is waiting".
8. **A first-time hint for each HUD button.** A one-time pulse and a short line ("Hire your first employee here") the first time a button matters. Showing it only once across sessions needs saved data: request to gameplay (R2) before building; a session-only version can come first.

## Doing now

waiting for review of PR #53

## Last PR

PR #53 (`ux-goal-chain`, backlog item 2, U1), open: https://github.com/mattimarca02/startup-to-ipo/pull/53. Before it: PR #48, merged 2026-10-18 09:18 UTC.

## Last report

2026-10-18 10:24 UTC. I merged main (acab027) into `ux-goal-chain` with no conflicts and opened PR #53: https://github.com/mattimarca02/startup-to-ipo/pull/53. With this change, the Goals card draws only the goals the server marks with `OnboardingGoalShown_<key>`, in the order of `activeGoals()`, with `min(ShowAtOnce, #activeGoals())` rows. A server that marks nothing gets the old first-goals card. The PR changes OnboardingClient.lua, the new tools/onboarding_client_test.luau, tools/hud_test.py, and the ux check in tools/daily_test.py. With `ChainEnabled` off, players see the same card as today. My claim rows went straight to main.

Tests (Luau 0.742, one at a time): hud 1073 (69/69, coupling 26/26), claim button 129 (28/28), Goals card 27 (9/9), daily all green, world 380 (101/101), icon 371 (68/68), shop_ux 6308 (103/103), lobby 155 (63/63), building 1407 (46/46), onboarding 78 (16/16). The Studio step is below (OnboardingClient, sha256 7c69d99f…, 14691 bytes). No new requests. Waiting for the owner: the review and merge of PR #53. After the merge, gameplay can turn `ChainEnabled` on, and my next item is 4 (tap targets, starting with the Goals card's X).

Earlier run (about 10:10 UTC): stopped before any work because the permission check refused git commands; nothing was changed.

2026-10-18 09:10 UTC. The owner merged PR #44 at 08:53 UTC. Its two claim rows (ClaimButtonClient, tools/claim_button_test.luau) were already free on main, because the merge took CONTRIBUTING.md from main. I brought main into `ux-sync-history` (backlog item 5, built in the previous run) and opened PR #48: https://github.com/mattimarca02/startup-to-ipo/pull/48. It changes only tools/hud_test.py and tools/shop_ux_test.py. They now check docs/STUDIO_SYNC_HUD.md and docs/STUDIO_SYNC_SHOP.md against IpoClient, ShopClient and ShopLayout as they were at `645393a`, so a later edit of those scripts no longer fails either suite. Per the owner's new note, the PR carries no claim rows: I pushed my two claim rows (hud_test, shop_ux_test) and this file straight to main, and this time the push worked.

Tests (Luau 0.742, one at a time, with main 244fbd7 merged in): hud 1073 (69/69, coupling 26/26), claim button 129 (28/28), daily 2980 (294/294), world 380 (101/101), icon 371 (68/68), shop_ux 6308 (103/103), lobby 155 (63/63), building 1407 (46/46), onboarding 61 (10/10). All green. No Studio steps for #48 (test files only). #44's step is below and in quality's Batch 1.

Next: backlog item 2 (U1). PR #43 is merged, so `OnboardingConfig.activeGoals` is on main and U1 is no longer blocked. I'll build it when #48 is merged. Requests: none new. Waiting for the owner: the review and merge of PR #48.

2026-10-18 10:05 UTC: the owner merged PR #48 at 09:18 UTC. I released my two claim rows (tools/hud_test.py, tools/shop_ux_test.py) and stopped the check-ins. #48 has no Studio steps. The next run starts backlog item 2 (U1: the Goals card draws only the goals the server marks as shown, in `activeGoals()` order); the gameplay lane waits for it before turning `ChainEnabled` on.

## Requests to other lanes

- **To gameplay (U1): PR #53**; once it is merged, `ChainEnabled` can go on in your one-line PR.
- **To quality:** once `ux-goal-chain` is merged: README's tools row for tools/onboarding_client_test.luau (run by tools/hud_test.py) and the Studio step above in the batch.
- **R1, to gameplay (tools/lobby_test.py): DONE (PR #38, merged).** its "Lobby all" doc checks (`ALL_SCRIPTS`) compare docs/STUDIO_SYNC_LOBBY.md with today's bytes of ShopClient, IpoClient, LobbyClient, EmployeeClient, BuildingClient (and TycoonCore, ShopServer, WorldArt, WorldVisuals, PlotVisuals, ...). That doc is history now (lobby-all is merged; new Studio steps go to docs/STUDIO_SYNC_BATCH.md), so any later edit of one of those files fails lobby_test, in every lane. Please check that section against the files at the lobby-all merge commit `2df1410`, the way the L1 section uses `L1_COMMIT = "f6a546f"`. 
- **R2, to gameplay (later, item 6):** a place to save which HUD hints a player has seen (a list of short keys). Rule A10 says a new top-level section; it needs the owner's written OK. Not needed yet (item 8).
- **To quality:** when PR `ux-claim-button` is merged, README.md and CLAUDE.md need the new LocalScript `ClaimButtonClient` (StarterPlayer > StarterPlayerScripts, display only, no remote; it presses the server's own claim prompt) and its Studio step goes in the batch.

## Studio steps (merged PRs not yet in Studio)

`ux-goal-chain` (item 2), once it is merged: paste OnboardingClient.lua into the LocalScript `OnboardingClient` (StarterPlayer > StarterPlayerScripts): sha256 `7c69d99f8c2c02667100c0538b238250e7f6a71c0713cdb090dfc7862cdffdb5`, 14691 bytes. F5 as a new player: once the free egg hatches the card shows "Hire 3 employees" and "Reach Seed stage" as before, no errors in Output.

PR #44 (merged 2026-10-18): paste ClaimButtonClient.lua into the LocalScript `ClaimButtonClient` (sha256 `b00fcd8637d378eca02d3e6b4b856ee9fea8d184ea3086a2031d0eee124817c4`, 10261 bytes; it replaces PR #35's version), then steps 3 and 4 below.

PR #35, once it is merged:
1. Create a LocalScript named exactly `ClaimButtonClient` in StarterPlayer > StarterPlayerScripts.
2. Paste ClaimButtonClient.lua into it (sha256 `494d14bdd2843e49606a7a339793e9b4c7840ea0cc08f967f5f7c3863bed2b00`, 7525 bytes).
3. Press F5 with the claim off: nothing new shows and the Output window has no errors.
4. Optional, never published: set ClaimEnabled to true, then use Test > Device with a phone in portrait and landscape, walk to a free garage and tap the button. Set ClaimEnabled back to false afterwards.
