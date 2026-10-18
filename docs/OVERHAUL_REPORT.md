# Overhaul report (2026-10-18)

The owner's playtest of 2026-10-18 (two players, the claim on) gave seven points; docs/OVERHAUL_PLAN.md turned them into six phases, one branch and one pull request each, stacked: `overhaul-phase1` (#55) → `phase2` (#56) → `phase3` (#57) → `phase4` (#58) → `phase5` (#59) → `phase6`. Merge them in that order. Nothing was published; every changed script was pushed to the Team Create place through the Studio MCP and hash-checked (docs/STUDIO_SYNC_BATCH.md Batches 3 to 7 (phase 6 changed no script)), and the Studio-only settings are recorded in docs/STUDIO_SYNC.md (b).

## Done, by the owner's points

| # | The point | What changed | Phase / PR |
|---|---|---|---|
| 6 | After claiming, other garages' FREE markers must go for that player | `LobbyClient` hides the other garages' FREE signs, lamps and claim prompts on that client only; the server still refuses a second claim | 1 / #55 |
| 7 | The empty entrance sign with the arrow | Every stage's facade sign carries a SurfaceGui the server writes: FREE / "Claim this garage", the company name and the stage, "Moving in..." / "Closing..." | 1 / #55 |
| 2 | Walking through benches and trees | `WorldVisuals` builds one invisible solid box per trunk, lamp post, bench, planter, sign post, fountain basin and pillar, arch post (62 boxes); bushes stay walk-through | 1 / #55 |
| 3 | The garage is invisible from inside; a real building | The occlusion fade: only the shell parts between the camera and the character turn see-through, so inside you see walls, ceiling, door and windows; one ceiling light per building; a stage-up moment (camera look at the facade, sound, toast "Seed reached! Your Garage becomes a Small Office") | 2 / #56 |
| 4 | Desks appear only when hiring | A room starts with no hire desk; one desk per hire pops in at its spot, a see-through "next hire" desk marks the next; derived from the team, never saved | 3 / #57 |
| 5 | Meaning: what, why, what's next | The welcome card on the plaza (the story in four lines), the goal chain on (upgrades, hires, the Server Rack, every funding round, the IPO), a "New goal" pop-up with the why for every goal that appears | 4 / #58 |
| 1 | Graphics flat and cheap | Textured ground (Grass lawns, hills and Baseplate; Concrete paths and kerbs; leafy crowns), facade depth on every office (canopies, sills, string course, pilasters, fins, floor lines, gold lines), lighting retuned for phones (Future by hand) | 5 / #59 |
| phone | Phone and UI polish | An audit in Studio play (1193x434 viewport, the short-screen layout): the five HUD buttons and the gift chip in one row at the top, every window (Shop, Eggs/Team, Poach, IPO, Daily) the same 640x399 box, one window at a time (opening one closes the other, `PlayerGui` attribute `OpenPanel`), every pop-up centered at the bottom in its lane (-16, -72, -128, -184, -240), nothing off-screen, nothing in the thumbstick's or the jump button's zone, icons and labels on every HUD button. No defect found, so no client changed; the portrait sizes are covered by the suites (hud_test 1,073 HUD checks, shop_ux at phone sizes, daily_test's tray at 320x568 to 844x390). The real Test > Device pass stays with the owner. | 6 / #60 |

Also fixed on the way: four scripts of PRs #51 to #53 had never been pasted into Studio (now pushed, Batch 3); `Clouds` moved from `Lighting.Sky` to `Workspace.Terrain` (it never showed); Max Players is still 60 in Studio and must be 6 (Creator Hub, by hand).

## Not done

- **Richer interiors per stage** (a rug, a plant and a lamp more): the rooms are at 258 of 260 parts in the full-room test, so nothing fits without raising the room budget (a rule change for a later PR). The live rooms are lighter since phase 3 (desks only per hire).
- **Terrain** for the ground: a Grass-material Baseplate instead.
- **Two-player and phone playtests** of each phase: left to the owner (the MCP drives one client, and its screen captures come back white after the first frame, so every check was by data, not by eye).
- **Economy numbers**: nothing retuned (the brief: only with the owner's OK). The chain's pacing was checked by reading against the plan's minute table.
- **Customer calls** stay Studio-only (`TaskConfig.StudioOnly`): live, the chain skips the two call goals.

## Rule changes (all in CLAUDE.md, each in its PR)

1. The world's Solid group (invisible boxes inside the decor's footprints; `tools/world_test.py` "solid"); the preview pin 268 → 320 parts.
2. The facade sign's SurfaceGui is the building's one gui; stage 2 has Blocks (the kit-extras check ignores Blocks).
3. The occlusion fade replaces the whole-shell fade (building_test's client tests rewritten); one `rbxasset://sounds/` in BuildingClient allowed; `ShopServer.notify` rows for the stage-up toast.
4. Hire desks follow the team; daily_test's garage harness gives the plot every desk before comparing rooms.
5. `OnboardingConfig.ChainEnabled` ships true; every goal has a why; the welcome card.
6. `WorldArt.Materials` for the flat pieces; the facade Blocks per stage (never named "Band"); the Studio lighting and Baseplate settings.

## Known issues

- Max Players is 60 in the place (by hand → 6).
- `Lighting.Technology` can't be read or set by a script: set Future by hand (ShadowMap if a phone is slow).
- The integration patch note in world_test (not exact for this TycoonCore) is older than this work and is "fine until merge time".
- Studio prints Roblox's own UIBlox "FoundationProvider not found" warnings on every play: not ours.

## Frame rate

Measured on the client in Studio play through the MCP on the Mac, six garages at stage 1 plus the world: 1,702 parts, 22 lights, **15 fps** at the plaza and by a garage, before and after the materials (Studio renders slowly while its window is not in front; the MCP drives it from the terminal). This is not a phone number: read the real one in a playtest (Shift+F5) and on Test > Device. Budgets: a building is at most 160 parts (stage 5: 159), a full room 260, the plaza 480 (398 built), six garages at the biggest stage plus the plaza under 3,000 (building_test).

## Publish checklist (only when the owner decides)

1. Merge #55 → #56 → #57 → #58 → #59 → #60, in order; `git pull` main.
2. In Studio: File > Save to Roblox (the pushed scripts and the settings are in the Team Create place; the hash blocks of Batches 3 to 7 (phase 6 changed no script) must all print ALL OK).
3. By hand: Lighting > Technology = Future; Creator Hub > Max Players = 6; delete `Workspace.PREVIEW_STAGES` / `PREVIEW_WORLD` if present; no breakpoints.
4. Test > Device, portrait and landscape; Test > Clients and Servers with 2 players.
5. File > Publish to Roblox, then Creator Hub > the place > **Shut down all servers** (LobbyConfig and the other ModuleScripts are read when a server starts).
