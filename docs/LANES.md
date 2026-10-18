# Lanes: six Claude sessions working in parallel

Added 2026-10-17 by the owner's request. Six Claude Code sessions ("lanes") work on separate parts of the game at the same time. This file says who owns what, how lanes ask each other for changes, and how work reaches `main` and Studio. CLAUDE.md and CONTRIBUTING.md still apply in full; this file adds to them.

## The six lanes

| Lane | Branch prefix | Owns (may edit) | Model, effort |
|---|---|---|---|
| **interiors**: the furniture inside the room, different per funding stage | `interiors-` | PlotArt.lua, PlotVisuals.lua, docs/PLOT_VISUALS.md, new interior files it creates | Opus, High |
| **building**: the outside of the five buildings | `building-` | PlotBuilding.lua, PlotBuildingVisuals.lua, BuildingClient.lua, tools/building_test.py, docs/KIT_MODELS.md, assets/kit/ | Opus, High |
| **world**: plaza, map, paths, decor, world icons | `world-` | WorldArt.lua, WorldVisuals.lua, LobbyConfig.lua, IconArt.lua, IconVisuals.lua, tools/world_test.py, tools/icon_test.py, tools/render_previews.py, docs/previews/ | Opus, Medium |
| **gameplay**: economy, tasks, progression, server rules | `gameplay-` | TycoonCore.lua, ShopServer.lua, ShopConfig.lua, EmployeeServer.lua, CreatureConfig.lua, CreatureModels.lua, PoachServer.lua, IpoServer.lua, IpoConfig.lua, DailyServer.lua, DailyConfig.lua, OnboardingServer.lua, OnboardingConfig.lua, TaskServer.lua, TaskConfig.lua, CompanyServer.lua, CompanyConfig.lua, SectorConfig.lua, tools/economy_sim.py, tools/first_hour_model.py, tools/lobby_test.py, tools/lobby_runtime.luau, the gameplay docs | Opus, High |
| **ux**: screens, HUD, on-screen buttons, phone layout | `ux-` | every `*Client.lua` (ShopClient, EmployeeClient, PoachClient, IpoClient, DailyClient, OnboardingClient, TaskClient, LobbyClient, ChatTags), ShopLayout.lua, tools/hud_test.py, tools/shop_ux_test.py, tools/lobby_client_test.luau | Opus, Medium |
| **quality**: reviews, fixes, cleanup, docs, the Studio batch | `quality-` | CLAUDE.md, ROADMAP.md, README.md, CONTRIBUTING.md, docs/STUDIO_SYNC_*.md, docs/PUBLISH_RULES.md; no game script unless its owner lane hands it over in writing | Opus, High |

A lane edits only the files it owns. Everything else is read-only for it. Two shared files are the exception, and both go straight to `main`, never through a PR: each lane's own `docs/lanes/<lane>.md`, and its own rows in `docs/lanes/claims.md` (the Ownership table).

**Shared test suite `tools/daily_test.py`.** Many lanes' rules are checked there. A lane may edit only the checks about its own files (for example interiors updates the room fingerprints after it changes a room on purpose, saying so in its PR). It does not claim the whole file: it writes `daily_test.py (checks of <lane>)` in its claim row (docs/lanes/claims.md). The second lane to merge rebases and re-runs every suite.

## Rules every lane follows

1. **Start:** `git pull` on main, read CLAUDE.md, this file, your lane file `docs/lanes/<lane>.md` and the other lanes' files (to see what they are doing and what they asked you). Work in your own git worktree.
2. **Claim** your files in the Ownership table, `docs/lanes/claims.md` (since 2026-10-18; it was in CONTRIBUTING.md before), pushed straight to `main`. Never edit a file another lane has claimed, even one you own here: wait or write a request. Release your rows when your PR is merged or abandoned, again straight to `main`.
   **A PR never carries claim-row edits: claim rows only go straight to `main`.** If a push to `main` is refused, `git pull --rebase` and push again; if it is still refused (a run without push rights to `main`), write the claim in your lane file's "Doing now" and say so in the PR text, never in the PR's diff. A PR whose diff touches `docs/lanes/claims.md` (or the old rows in CONTRIBUTING.md) gets FIX FIRST from the quality lane.
3. **One PR at a time per lane.** Small and finished: one feature per PR. Branch `<prefix><short-name>`. Rebase on the latest main before opening the PR and run **all** suites (daily, hud, world, icon, shop_ux, lobby, building): every check passes, every mutant caught by a named check.
4. **Never** touch Studio, never change the save format, the DataStore name or key, KNOWN_SECTIONS or a saving block. New saved data needs the owner's written OK and belongs to the gameplay lane (rule A10).
5. **Your lane file** `docs/lanes/<lane>.md` (only you edit it) holds: your backlog in order, what you are doing now, your last PR, **"Requests to other lanes"** (what you need changed in a file you don't own, with the exact reason) and **"Studio steps"** for your merged PRs (scripts to paste, objects to create). Keep it current; other lanes read it.
6. **Requests:** if you need a change in another lane's file, write it under "Requests to other lanes" and continue with what doesn't depend on it. When you start, read every lane file and handle the requests addressed to you first.
7. **When the PR is open:** stop and report in plain sentences: what changed, test counts, Studio steps, requests you made. Do not merge. The quality lane reviews, the owner merges.

## How work reaches main and Studio

1. A lane opens a PR. The quality lane reviews it read-only (all suites, rules, the diff) and writes the verdict in `docs/lanes/quality.md`: merge, fix first, or redo.
2. The owner merges approved PRs one at a time. Before each merge the PR must be up to date with main (the lane rebases if not).
3. Studio: no lane touches it. The quality lane collects the "Studio steps" of merged PRs into one batch doc, `docs/STUDIO_SYNC_BATCH.md` (scripts to paste with sha256, a hash block that prints ALL OK, checks, playtests). The owner runs it in one VS Code session on the published place, never Publish.
