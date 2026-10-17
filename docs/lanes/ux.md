# Lane: ux

Only the ux lane edits this file. See docs/LANES.md.

## Backlog (in order)

1. **"Claim garage" button on phones** (branch `ux-claim-button`). A new display-only LocalScript `ClaimButtonClient`: while the server's "Claim garage" prompt is shown on a phone (touch input) and the player has no garage, a big button (at least 240 x 60) sits at the bottom center, above the pop-ups. Tapping it presses the prompt itself (`InputHoldBegin`, then `InputHoldEnd` after the hold time), so the server checks everything as it does today (distance, rate, the garage's state): no new remote, no server change. It hides while a window is open (`OpenPanel`) and with the claim off (`LobbyConfig.ClaimEnabled`, which ships off: nothing changes for live players until the owner turns it on). New file because `LobbyClient.lua` is hash-pinned by tools/lobby_test.py (request R1 below).
2. **U1 from gameplay: the goal chain in the Goals card (OnboardingClient).** Draw only the goals with the player attribute `OnboardingGoalShown_<key> == true`, in the order of `OnboardingConfig.activeGoals()`, and size the card for `math.min(OnboardingConfig.ShowAtOnce, #activeGoals())` rows, then count rows the same way in tools/hud_test.py's `onboarding_goal_count`. Next after PR #35 (it blocks gameplay turning `ChainEnabled` on). Needs `activeGoals` and `ShowAtOnce` on main first (they are on `gameplay-goal-chain`, not merged yet). Item 4's X fix goes in the same file, so it waits until this one is done.
3. **Quality follow-ups on ClaimButtonClient and hud_test (not blocking #35).** (a) Keep a set of the claim prompts shown for touch and label the button with the nearest one, so when two show at once and the newer one hides first, the button doesn't disappear while the other is still shown. (b) The HUD mutant "event not disconnected" needs about 3 GB of memory and crashes when several suites run in parallel: cap its loop or shrink the fake. Small, one PR.
4. **Tap targets at least 40 x 40 everywhere.** The Goals tracker's X (OnboardingClient, 30 x 26 today) gets a 44 x 44 hit area without moving the card; a static check in tools/hud_test.py that every TextButton/ImageButton with a fixed size in the clients is at least 40 px on each side.
5. **Unpin my tests' Studio-sync hashes.** tools/hud_test.py (IpoClient in docs/STUDIO_SYNC_HUD.md) and tools/shop_ux_test.py (ShopClient and ShopLayout in docs/STUDIO_SYNC_SHOP.md) compare those docs with today's files, so any later edit of IpoClient or ShopClient fails them. Check them against the files at the commit the doc was written for (like lobby_test's L1 section), so the docs stay history. Needed before items 6 to 8 (which touch IpoClient and ShopClient); also needs R1.
6. **One place for pop-ups.** Seven toasts sit at seven heights today (Shop, IPO and Task at -16, Employee -72, Poach -128, Onboarding -184, Daily -240) with different sizes and fonts. Give them one style (size, font, colour, time) and a fixed stack so two never cover each other, on both phone sizes.
7. **Clearer HUD buttons.** EGGS, SHOP, TEAM, POACH, IPO: the same size, icon plus a short label that fits at 64 x 64 (short screens) and 76 x 76, one badge style for "something is waiting".
8. **A first-time hint for each HUD button.** A one-time pulse and a short line ("Hire your first employee here") the first time a button matters. Showing it only once across sessions needs saved data: request to gameplay (R2) before building; a session-only version can come first.

## Doing now

waiting for review of PR #35

## Last PR

PR #35 (`ux-claim-button`): https://github.com/mattimarca02/startup-to-ipo/pull/35

## Last report

2026-10-17. I filled the backlog (6 items) and built item 1. PR #35 adds a new display-only LocalScript, `ClaimButtonClient`. On a phone, while the server's "Claim garage" prompt is shown and the player has no garage, a big green button appears at the bottom of the screen. Tapping it presses that same prompt, so the server checks everything exactly as it does today. It adds no remote and changes no server file. It hides while a window is open, and nothing shows with `LobbyConfig.ClaimEnabled` off (as it ships). I made it a new file because LobbyClient is hash-pinned by tools/lobby_test.py (request R1, which gameplay has picked up).

Tests (Luau 0.742): tools/hud_test.py now also runs the real client in a fake (tools/claim_button_test.luau). That gives 117 checks, 21 of 21 mutants caught and the self-test passing; the existing HUD checks also pass (1073 checks, 69/69 mutants). All other suites are green: daily 2822 checks with 281/281 mutants, world 366 + 93/93, icon 371 + 68/68, shop_ux 6306 + 103/103, lobby 154 + 64/64, building 1278 + 40/40.

Studio steps are in the PR and below. My requests: R1 to gameplay, R2 later, and to quality the README and CLAUDE.md listing of the new script. Waiting for the owner: the review and merge of PR #35. ClaimEnabled stays off (owner decision 9), so the button is only visible after the owner turns the claim on.

Check-in 2026-10-17 17:05 UTC: PR #35 still has no review (the quality lane is reviewing #35 to #40). I added gameplay's request U1 to the backlog as item 2. I'll build it after #35, once `activeGoals` is on main. I read the owner's new rule (push after every step) and will follow it.

Check-in 2026-10-17 21:05 UTC: the quality lane's verdict on PR #35 is MERGE, after #38 and once #35 is up to date with main. I merged main into `ux-claim-button` (merge commit 0d6be20, no force-push), so it's up to date now. ClaimButtonClient.lua didn't change (sha256 `494d14bd…`, 7525 bytes). On that head, hud passes (1073 checks + 117 claim-button checks; 69/69 and 21/21 mutants) and daily passes. Run alone, lobby still fails on the old doc pins until #38 merges, as the verdict expects. I added the verdict's two non-blocking notes to the backlog as item 3. Waiting for the owner: merge #38, then #35. If #38 lands first, I bring main in again and re-run the suites.

## Requests to other lanes

- **R1, to gameplay (tools/lobby_test.py):** its "Lobby all" doc checks (`ALL_SCRIPTS`) compare docs/STUDIO_SYNC_LOBBY.md with today's bytes of ShopClient, IpoClient, LobbyClient, EmployeeClient, BuildingClient (and TycoonCore, ShopServer, WorldArt, WorldVisuals, PlotVisuals, ...). That doc is history now (lobby-all is merged; new Studio steps go to docs/STUDIO_SYNC_BATCH.md), so any later edit of one of those files fails lobby_test, in every lane. Please check that section against the files at the lobby-all merge commit `2df1410`, the way the L1 section uses `L1_COMMIT = "f6a546f"`. Until then the ux lane does not edit IpoClient, ShopClient, EmployeeClient or LobbyClient.
- **R2, to gameplay (later, item 6):** a place to save which HUD hints a player has seen (a list of short keys). Rule A10 says a new top-level section; it needs the owner's written OK. Not needed yet (item 8).
- **To quality:** when PR `ux-claim-button` is merged, README.md and CLAUDE.md need the new LocalScript `ClaimButtonClient` (StarterPlayer > StarterPlayerScripts, display only, no remote; it presses the server's own claim prompt) and its Studio step goes in the batch.

## Studio steps (merged PRs not yet in Studio)

PR #35, once it is merged:
1. Create a LocalScript named exactly `ClaimButtonClient` in StarterPlayer > StarterPlayerScripts.
2. Paste ClaimButtonClient.lua into it (sha256 `494d14bdd2843e49606a7a339793e9b4c7840ea0cc08f967f5f7c3863bed2b00`, 7525 bytes).
3. Press F5 with the claim off: nothing new shows and the Output window has no errors.
4. Optional, never published: set ClaimEnabled to true, then use Test > Device with a phone in portrait and landscape, walk to a free garage and tap the button. Set ClaimEnabled back to false afterwards.
