# Lane: ux

Only the ux lane edits this file. See docs/LANES.md.

## Backlog (in order)

1. **"Claim garage" button on phones** (branch `ux-claim-button`). A new display-only LocalScript `ClaimButtonClient`: while the server's "Claim garage" prompt is shown on a phone (touch input) and the player has no garage, a big button (at least 240 x 60) sits at the bottom center, above the pop-ups. Tapping it presses the prompt itself (`InputHoldBegin`, then `InputHoldEnd` after the hold time), so the server checks everything as it does today (distance, rate, the garage's state): no new remote, no server change. It hides while a window is open (`OpenPanel`) and with the claim off (`LobbyConfig.ClaimEnabled`, which ships off: nothing changes for live players until the owner turns it on). New file because `LobbyClient.lua` is hash-pinned by tools/lobby_test.py (request R1 below).
2. **Tap targets at least 40 x 40 everywhere.** The Goals tracker's X (OnboardingClient, 30 x 26 today) gets a 44 x 44 hit area without moving the card; a static check in tools/hud_test.py that every TextButton/ImageButton with a fixed size in the clients is at least 40 px on each side.
3. **Unpin my tests' Studio-sync hashes.** tools/hud_test.py (IpoClient in docs/STUDIO_SYNC_HUD.md) and tools/shop_ux_test.py (ShopClient and ShopLayout in docs/STUDIO_SYNC_SHOP.md) compare those docs with today's files, so any later edit of IpoClient or ShopClient fails them. Check them against the files at the commit the doc was written for (like lobby_test's L1 section), so the docs stay history. Needed before items 4 to 6 (which touch IpoClient and ShopClient); also needs R1.
4. **One place for pop-ups.** Seven toasts sit at seven heights today (Shop, IPO and Task at -16, Employee -72, Poach -128, Onboarding -184, Daily -240) with different sizes and fonts. Give them one style (size, font, colour, time) and a fixed stack so two never cover each other, on both phone sizes.
5. **Clearer HUD buttons.** EGGS, SHOP, TEAM, POACH, IPO: the same size, icon plus a short label that fits at 64 x 64 (short screens) and 76 x 76, one badge style for "something is waiting".
6. **A first-time hint for each HUD button.** A one-time pulse and a short line ("Hire your first employee here") the first time a button matters. Showing it only once across sessions needs saved data: request to gameplay (R2) before building; a session-only version can come first.

## Doing now

ux-claim-button - started 2026-10-17 15:44 UTC

## Last PR

none

## Requests to other lanes

- **R1, to gameplay (tools/lobby_test.py):** its "Lobby all" doc checks (`ALL_SCRIPTS`) compare docs/STUDIO_SYNC_LOBBY.md with today's bytes of ShopClient, IpoClient, LobbyClient, EmployeeClient, BuildingClient (and TycoonCore, ShopServer, WorldArt, WorldVisuals, PlotVisuals, ...). That doc is history now (lobby-all is merged; new Studio steps go to docs/STUDIO_SYNC_BATCH.md), so any later edit of one of those files fails lobby_test, in every lane. Please check that section against the files at the lobby-all merge commit `2df1410`, the way the L1 section uses `L1_COMMIT = "f6a546f"`. Until then the ux lane does not edit IpoClient, ShopClient, EmployeeClient or LobbyClient.
- **R2, to gameplay (later, item 6):** a place to save which HUD hints a player has seen (a list of short keys). Rule A10 says a new top-level section; it needs the owner's written OK. Not needed yet.
- **To quality:** when PR `ux-claim-button` is merged, README.md and CLAUDE.md need the new LocalScript `ClaimButtonClient` (StarterPlayer > StarterPlayerScripts, display only, no remote; it presses the server's own claim prompt) and its Studio step goes in the batch.

## Studio steps (merged PRs not yet in Studio)

none
