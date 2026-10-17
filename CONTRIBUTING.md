# Working together

Two people, one Roblox place (Team Create) and one GitHub repo. These rules stop us from overwriting each other's work.

## The rules

1. **Pull before you start.** Always begin with the latest `main`.
2. **One branch per milestone or feature.** Never commit code straight to `main`.
3. **Never edit the same script at the same time.** Claim a script in the [Ownership](#ownership) table before touching it, and leave scripts the other person has claimed alone.
4. **Small commits.** Make one commit per working step, with a message saying what changed and why.
5. **Merge through a pull request.** The other person looks at it before it goes into `main`.
6. **Never commit secrets.** `.env` and `.env.txt` are ignored by git. Keep API keys out of code, Studio and chat.

## A change from start to finish

1. **Get the latest `main`:**
   ```
   git checkout main
   git pull
   ```

2. **Claim your scripts.** In the [Ownership](#ownership) table below, put your name, branch and date next to each script you'll change. This table is the only thing you may push straight to `main`:
   ```
   git add CONTRIBUTING.md
   git commit -m "Claim EmployeeServer for milestone-4-poaching"
   git push
   ```
   Tell your teammate. If a script you need is already claimed, wait or talk first.

3. **Make your branch.** Use lowercase and dashes:
   - `milestone-<number>-<name>`, for example `milestone-4-poaching`
   - `feature-<name>`, for example `feature-daily-reward`
   - `fix-<name>`, for example `fix-offline-cash`

   ```
   git checkout -b milestone-4-poaching
   ```

4. **Work and test.** Change the scripts, playtest in Studio (F5) and check the Output window for red errors. Keep Studio and the `.lua` files matching (see [the sync rule](#keeping-studio-and-the-repo-in-sync)).

   Studio playtests need **Enable Studio Access to API Services** turned ON (Game Settings > Security). With it off, saves can't load and the 6 s load retry kicks you out of the playtest.

5. **Commit small.** Commit each time something works:
   ```
   git status
   git add EmployeeServer.lua
   git commit -m "Poaching: steal chance depends on rarity"
   ```

6. **Push and open a pull request.** Pull with `git pull origin main` first. Then:
   ```
   git push -u origin milestone-4-poaching
   gh pr create --fill
   ```
   In the description, write what changed and how to test it in Studio.

7. **Review.** The other person reads the **Files changed** tab, tries it in Studio if needed, and approves or comments.

8. **Merge.** On GitHub, click **Squash and merge**, then **Delete branch**. From the terminal it's `gh pr merge --squash --delete-branch`.

9. **Finish up.** Both people run:
   ```
   git checkout main
   git pull
   ```
   Clear your rows in the Ownership table and push that.

**If git says CONFLICT or refuses to push,** stop and ask your teammate or Claude Code. Never use `git push --force` on `main`.

## Keeping Studio and the repo in sync

The repo is the official copy of every script. Team Create is the live place we both playtest. Nothing syncs by itself: a change exists in one place until someone copies it to the other.

- **Studio → repo:** once a change works in a playtest, copy the whole script into its `.lua` file and commit it on your branch.
- **Repo → Studio:** when a `.lua` file changes outside Studio (Claude Code, a fix during review, a revert), paste it into the Studio script with the same name straight away, and playtest.
- **Unclaimed scripts** must be identical in Studio and on `main`. If they differ, the `main` version wins.
- **Before merging a pull request,** the author checks that each changed script in Studio matches the pull request.

To copy a script, double-click it in Studio's Explorer, press **Ctrl+A** then **Ctrl+C** (**Cmd** on Mac), and paste it over the whole `.lua` file. For the other direction, paste the file into the script.

If Studio lists your script in the **Drafts** window (**View → Drafts**), right-click it and choose **Commit**, so the live place gets it.

## Ownership

Whoever is named here is the only person editing that script right now. Claim a script before changing it and clear it when your pull request is merged. Add a row when you create a new script.

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
| IpoConfig | ReplicatedStorage | free | | |
| IpoClient | StarterPlayerScripts | free | | |
| DailyServer | ServerScriptService | free | | |
| DailyConfig | ReplicatedStorage | free | | |
| DailyClient | StarterPlayerScripts | free | | |
| OnboardingServer | ServerScriptService | gameplay lane | gameplay-goal-chain | 2026-10-17 |
| OnboardingConfig | ReplicatedStorage | gameplay lane | gameplay-goal-chain | 2026-10-17 |
| OnboardingClient | StarterPlayerScripts | free | | |
| tools/economy_sim.py | (repo only) | free | | |
| docs/ECONOMY.md | (repo only) | free | | |
| docs/PUBLISH_RULES.md | (repo only) | free | | |
| docs/ACTIVE_LOOPS_PROPOSAL.md | (repo only) | free | | |
| docs/LONG_GAME_PROPOSAL.md | (repo only) | free | | |
| TaskConfig | ReplicatedStorage | free | | |
| TaskServer | ServerScriptService | free | | |
| TaskClient | StarterPlayerScripts | free | | |
| ROADMAP.md | (repo only) | free | | |
| CLAUDE.md | (repo only) | free | | |
| PlotVisuals | ServerScriptService | free | | |
| PlotArt | ServerScriptService | free | | |
| README.md | (repo only) | free | | |
| docs/PLOT_VISUALS.md | (repo only) | free | | |
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
| tools/hud_test.py | (repo only) | ux lane (Claude) | ux-claim-button | 2026-10-17 |
| docs/STUDIO_SYNC_HUD.md | (repo only) | free | | |
| WorldArt | ServerScriptService | Claude (world lane) | world-ring-plaza | 2026-10-17 |
| WorldVisuals | ServerScriptService | Claude (world lane) | world-ring-plaza | 2026-10-17 |
| IconArt | ReplicatedStorage | free | | |
| IconVisuals | ReplicatedStorage | free | | |
| tools/world_test.py | (repo only) | Claude (world lane) | world-ring-plaza | 2026-10-17 |
| tools/icon_test.py | (repo only) | free | | |
| tools/render_previews.py | (repo only) | Claude (world lane) | world-ring-plaza | 2026-10-17 |
| docs/previews/*.svg | (repo only) | Claude (world lane) | world-ring-plaza | 2026-10-17 |
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
| tools/lobby_test.py | (repo only) | gameplay lane | gameplay-lobby-test-history | 2026-10-17 |
| docs/STUDIO_SYNC_LOBBY.md | (repo only) | free | | |
| docs/BUILDING_STAGES_PROPOSAL.md | (repo only) | free | | |
| docs/MODEL_ASSETS_PLAN.md | (repo only) | free | | |
| docs/LOBBY_ALL_PROGRESS.md | (repo only) | @mattimarca02 (Claude Code) | lobby-studio-sync-notes | 2026-10-17 |
| PlotBuilding | ServerScriptService | building lane (Claude) | building-garage-roof | 2026-10-17 |
| PlotBuildingVisuals | ServerScriptService | building lane (Claude) | building-garage-roof | 2026-10-17 |
| BuildingClient | StarterPlayerScripts | free | | |
| tools/building_test.py | (repo only) | building lane (Claude) | building-garage-roof | 2026-10-17 |
| docs/BUILDING_PASS_PROPOSAL.md | (repo only) | free | | |
| docs/BUILDING_PASS_NOTES.md | (repo only) | free | | |
| docs/STUDIO_SYNC_BUILDING.md | (repo only) | free | | |
| docs/building_pass_integration.patch | (repo only) | free | | |
| LobbyConfig | ReplicatedStorage | free | | |
| LobbyClient | StarterPlayerScripts | free | | |
| docs/KIT_MODELS.md | (repo only) | building lane (Claude) | building-garage-roof | 2026-10-17 |
| tools/lobby_runtime.luau | (repo only) | free | | |
| tools/lobby_client_test.luau | (repo only) | free | | |
| tools/onboarding_test.py | (repo only) | gameplay lane | gameplay-goal-chain | 2026-10-17 |
| ClaimButtonClient | StarterPlayerScripts | ux lane (Claude) | ux-claim-button | 2026-10-17 |
| tools/claim_button_test.luau | (repo only) | ux lane (Claude) | ux-claim-button | 2026-10-17 |
