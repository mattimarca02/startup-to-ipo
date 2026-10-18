# Claims: who is editing which file right now

The one Ownership table of the repo (moved here from CONTRIBUTING.md on 2026-10-18, the owner's request in docs/lanes/owner.md). Whoever is named in a row is the only one editing that file right now. Claim a file before changing it, release it (`free`, branch and date emptied) when your pull request is merged or abandoned, add a row when you create a new file.

**This file only goes straight to `main`** (`git pull`, edit your own rows, commit, `git push`; on a refused push, `git pull --rebase` and push again). **A pull request never changes it**: a branch that touched it would conflict with every other lane's claim. Edit only your own rows; a row someone else holds is theirs until they release it. Nothing else in the repo is pushed straight to `main` this way, except each lane's own `docs/lanes/<lane>.md`.

Team: @mattimarca02 (owner) · @wildsheepchaser

| Script | Studio location | Being edited by | Branch | Since |
|---|---|---|---|---|
| TycoonCore | ServerScriptService | free | | |
| ShopServer | ServerScriptService | free | | |
| EmployeeServer | ServerScriptService | free | | |
| ShopConfig | ReplicatedStorage | free | | |
| CreatureConfig | ReplicatedStorage | free | | |
| CreatureModels | ReplicatedStorage | free | | |
| ShopClient | StarterPlayerScripts | free | | |
| EmployeeClient | StarterPlayerScripts | free | | |
| ChatTags | StarterPlayerScripts | free | | |
| sync_monetization.py | (repo only) | free | | |
| PoachServer | ServerScriptService | free | | |
| PoachClient | StarterPlayerScripts | free | | |
| IpoServer | ServerScriptService | free | | |
| tools/daily_test.py | (repo only) | free | | |
| tools/daily_test.py (checks of gameplay: daily) | (repo only) | Claude (gameplay lane) | gameplay-gift-first-pause | 2026-10-18 |
| tools/daily_test.py (checks of ux: the Goals card's row count) | (repo only) | Claude (ux lane) | ux-goal-chain | 2026-10-18 |
| tools/daily_test.py (checks of interiors: plot visuals) | (repo only) | Claude (interiors lane) | interiors-kit-garage | 2026-10-17 |
| IpoConfig | ReplicatedStorage | free | | |
| IpoClient | StarterPlayerScripts | free | | |
| DailyServer | ServerScriptService | Claude (gameplay lane) | gameplay-gift-first-pause | 2026-10-18 |
| DailyConfig | ReplicatedStorage | Claude (gameplay lane) | gameplay-gift-first-pause | 2026-10-18 |
| DailyClient | StarterPlayerScripts | free | | |
| OnboardingServer | ServerScriptService | free | | |
| OnboardingConfig | ReplicatedStorage | free | | |
| OnboardingClient | StarterPlayerScripts | Claude (ux lane) | ux-goal-chain | 2026-10-18 |
| tools/onboarding_client_test.luau | (repo only) | Claude (ux lane) | ux-goal-chain | 2026-10-18 |
| tools/economy_sim.py | (repo only) | free | | |
| docs/ECONOMY.md | (repo only) | free | | |
| docs/PUBLISH_RULES.md | (repo only) | Claude (quality lane) | quality-claim-on | 2026-10-18 |
| docs/ACTIVE_LOOPS_PROPOSAL.md | (repo only) | free | | |
| docs/LONG_GAME_PROPOSAL.md | (repo only) | free | | |
| TaskConfig | ReplicatedStorage | free | | |
| TaskServer | ServerScriptService | free | | |
| TaskClient | StarterPlayerScripts | free | | |
| ROADMAP.md | (repo only) | Claude (quality lane) | quality-claim-on | 2026-10-18 |
| CLAUDE.md | (repo only) | Claude (quality lane) | quality-claim-on | 2026-10-18 |
| PlotVisuals | ServerScriptService | Claude (interiors lane) | interiors-kit-garage | 2026-10-17 |
| PlotArt | ServerScriptService | Claude (interiors lane) | interiors-kit-garage | 2026-10-17 |
| README.md | (repo only) | Claude (quality lane) | quality-claim-on | 2026-10-18 |
| docs/PLOT_VISUALS.md | (repo only) | Claude (interiors lane) | interiors-kit-garage | 2026-10-17 |
| docs/STUDIO_SYNC.md | (repo only) | free | | |
| docs/CUSTOMIZE_PROPOSAL.md | (repo only) | free | | |
| docs/FUNDING_ROUNDS_PROPOSAL.md | (repo only) | free | | |
| docs/SECTORS_PROPOSAL.md | (repo only) | free | | |
| docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md | (repo only) | free | | |
| docs/GAMEPLAY_NOTES.md | (repo only) | free | | |
| docs/SOUND_PLAN.md | (repo only) | free | | |
| tools/first_hour_model.py | (repo only) | free | | |
| docs/SIMS_RESULTS.md | (repo only) | free | | |
| CompanyServer | ServerScriptService | free | | |
| CompanyConfig | ReplicatedStorage | free | | |
| SectorConfig | ReplicatedStorage | free | | |
| docs/CUSTOMIZE_PR1_NOTES.md | (repo only) | free | | |
| tools/hud_test.py | (repo only) | Claude (ux lane) | ux-goal-chain | 2026-10-18 |
| docs/STUDIO_SYNC_HUD.md | (repo only) | free | | |
| WorldArt | ServerScriptService | free | | |
| WorldVisuals | ServerScriptService | free | | |
| IconArt | ReplicatedStorage | free | | |
| IconVisuals | ReplicatedStorage | free | | |
| tools/world_test.py | (repo only) | free | | |
| tools/icon_test.py | (repo only) | free | | |
| tools/render_previews.py | (repo only) | free | | |
| docs/previews/*.svg | (repo only) | free | | |
| docs/SHOP_UX_PROPOSAL.md | (repo only) | free | | |
| docs/WORLD_PASS_PROPOSAL.md | (repo only) | free | | |
| docs/STUDIO_SYNC_WORLD.md | (repo only) | free | | |
| docs/world_pass_integration.patch | (repo only) | free | | |
| docs/WORLD_ICONS_NOTES.md | (repo only) | free | | |
| ShopLayout | ReplicatedStorage | free | | |
| tools/shop_ux_test.py | (repo only) | free | | |
| docs/STUDIO_SYNC_SHOP.md | (repo only) | free | | |
| docs/SHOP_BUILD_NOTES.md | (repo only) | free | | |
| docs/STUDIO_SYNC_MASTER.md | (repo only) | free | | |
| docs/LOBBY_GARAGE_PROPOSAL.md | (repo only) | free | | |
| tools/lobby_test.py | (repo only) | free | | |
| docs/STUDIO_SYNC_LOBBY.md | (repo only) | free | | |
| docs/BUILDING_STAGES_PROPOSAL.md | (repo only) | free | | |
| docs/MODEL_ASSETS_PLAN.md | (repo only) | free | | |
| docs/LOBBY_ALL_PROGRESS.md | (repo only) | @mattimarca02 (Claude Code) | lobby-studio-sync-notes | 2026-10-17 |
| PlotBuilding | ServerScriptService | free | | |
| PlotBuildingVisuals | ServerScriptService | free | | |
| BuildingClient | StarterPlayerScripts | free | | |
| tools/building_test.py | (repo only) | free | | |
| docs/BUILDING_PASS_PROPOSAL.md | (repo only) | free | | |
| docs/BUILDING_PASS_NOTES.md | (repo only) | free | | |
| docs/STUDIO_SYNC_BUILDING.md | (repo only) | free | | |
| docs/building_pass_integration.patch | (repo only) | free | | |
| LobbyConfig | ReplicatedStorage | Claude (quality lane) | quality-claim-on | 2026-10-18 |
| LobbyClient | StarterPlayerScripts | free | | |
| docs/KIT_MODELS.md | (repo only) | free | | |
| tools/lobby_runtime.luau | (repo only) | free | | |
| tools/lobby_client_test.luau | (repo only) | free | | |
| tools/onboarding_test.py | (repo only) | free | | |
| ClaimButtonClient | StarterPlayerScripts | free | | |
| tools/claim_button_test.luau | (repo only) | free | | |
| docs/STUDIO_SYNC_BATCH.md | (repo only) | Claude (quality lane) | quality-claim-on | 2026-10-18 |
