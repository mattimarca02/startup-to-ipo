# Claims: who is editing which file right now

The one Ownership table of the repo (moved here from CONTRIBUTING.md on 2026-10-18, the owner's request in docs/lanes/owner.md). Whoever is named in a row is the only one editing that file right now. Claim a file before changing it, release it (`free`, branch and date emptied) when your pull request is merged or abandoned, add a row when you create a new file.

**This file only goes straight to `main`** (`git pull`, edit your own rows, commit, `git push`; on a refused push, `git pull --rebase` and push again). **A pull request never changes it**: a branch that touched it would conflict with every other lane's claim. Edit only your own rows; a row someone else holds is theirs until they release it. Nothing else in the repo is pushed straight to `main` this way, except each lane's own `docs/lanes/<lane>.md`.

Team: @mattimarca02 (owner) · @wildsheepchaser

**2026-10-19, overhaul 2:** the owner session ("Claude (owner session 2)") holds every row below for docs/OVERHAUL2_PLAN.md, including the five rows the ux lane held for PR #64 (`OnboardingClient`, `LobbyClient`, `tools/hud_test.py`, `tools/onboarding_client_test.luau`, `tools/lobby_client_test.luau`): taken over because the lanes are paused (docs/lanes/owner.md). PR #64 must be rebased on overhaul 2 before it merges.

| Script | Studio location | Being edited by | Branch | Since |
|---|---|---|---|---|
| TycoonCore | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ShopServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| EmployeeServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ShopConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| CreatureConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| CreatureModels | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ShopClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| EmployeeClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ChatTags | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| sync_monetization.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| PoachServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| PoachClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| IpoServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/daily_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/daily_test.py (checks of gameplay: daily) | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/daily_test.py (checks of interiors: plot visuals) | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| IpoConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| IpoClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| DailyServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| DailyConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| DailyClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| OnboardingServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| OnboardingConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| OnboardingClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/onboarding_client_test.luau | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/economy_sim.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/ECONOMY.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/PUBLISH_RULES.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/ACTIVE_LOOPS_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/LONG_GAME_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| TaskConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| TaskServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| TaskClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ROADMAP.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| CLAUDE.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| PlotVisuals | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| PlotArt | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| README.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/PLOT_VISUALS.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/CUSTOMIZE_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/FUNDING_ROUNDS_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/SECTORS_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/GAMEPLAY_NOTES.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/SOUND_PLAN.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/first_hour_model.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/SIMS_RESULTS.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| CompanyServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| CompanyConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| SectorConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/CUSTOMIZE_PR1_NOTES.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/hud_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_HUD.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| WorldArt | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| WorldVisuals | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| IconArt | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| IconVisuals | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/world_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/icon_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/render_previews.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/previews/*.svg | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/SHOP_UX_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/WORLD_PASS_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_WORLD.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/world_pass_integration.patch | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/WORLD_ICONS_NOTES.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ShopLayout | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/shop_ux_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_SHOP.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/SHOP_BUILD_NOTES.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_MASTER.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/LOBBY_GARAGE_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/lobby_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_LOBBY.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/BUILDING_STAGES_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/MODEL_ASSETS_PLAN.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/LOBBY_ALL_PROGRESS.md | (repo only) | @mattimarca02 (Claude Code) | lobby-studio-sync-notes | 2026-10-17 |
| PlotBuilding | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| PlotBuildingVisuals | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| BuildingClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/building_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/BUILDING_PASS_PROPOSAL.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/BUILDING_PASS_NOTES.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_BUILDING.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/building_pass_integration.patch | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| LobbyConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| LobbyClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/KIT_MODELS.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/lobby_runtime.luau | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/lobby_client_test.luau | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/onboarding_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| ClaimButtonClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/claim_button_test.luau | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/hatch_reveal_test.luau | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/STUDIO_SYNC_BATCH.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/OVERHAUL2_PLAN.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| docs/OVERHAUL2_REPORT.md | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| OfficeConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| FounderConfig | ReplicatedStorage | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| FounderServer | ServerScriptService | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| FounderClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| IntroClient | StarterPlayerScripts | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
| tools/office_test.py | (repo only) | Claude (owner session 2) | overhaul2-phase1..6 | 2026-10-19 |
