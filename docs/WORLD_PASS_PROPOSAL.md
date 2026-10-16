# World pass proposal: from a green field to a startup street

> **Lobby L4 (2026-10-16, branch `lobby-all`):** the world is now built as a **ring** around a plaza in front of the VIP Lounge (docs/LOBBY_GARAGE_PROPOSAL.md section 4), only while `LobbyConfig.ClaimEnabled` is on: `WorldVisuals.ringSite` and `ringLayout`, wired in TycoonCore. The row layout below and docs/world_pass_integration.patch are **superseded** (the patch is never applied). The pieces, palette, materials, rules and named checks are reused. Picture: docs/previews/ring_topdown.svg.

Design (2026-10-06, branch `world-icons-pass`, from `main` `e3c9e67`; numbers updated after the build). Line numbers are `main` `e3c9e67`. Built as new files only: `WorldArt.lua` (data), `WorldVisuals.lua` (builder and checks), `tools/world_test.py`. Nothing is wired into the game: the one edit that would build it is `docs/world_pass_integration.patch`, not applied. **Studio fact** = placed by hand in Studio and measured by the owner (no script makes it). **(unverified)** = not checked in Studio.

Looks only, like the plot visuals: nothing is saved, sent through a remote or read back; nothing collides, is touched or stops a ray; no gameplay position moves; no `Touched` handler; no script inside the built models; nothing random; no asset.

## 1. The real geometry

| What | Where | Source |
|---|---|---|
| Plot spacing, plot count | `PLOT_SPACING = 90`, `MAX_PLOTS = 6` | TycoonCore.lua:74, 76 |
| Plot centers | x = -((6 - 1) x 90) / 2 + (slot - 1) x 90 = **-225, -135, -45, 45, 135, 225**; y 0.5; z **150** | TycoonCore.lua:123-126 |
| Plot floor | `Floor` 60 x 1 x 60 at the center: x center ± 30, y 0-1, **z 120-180** | TycoonCore.lua:736 |
| Front | **+Z**. The player lands at center + (0, 4, 12) looking at center + (0, 4, 24), toward the open front | TycoonCore.lua:694-701 |
| Signs | next-upgrade sign at center + (0, 0.5, 24), IPO sign at center + (21, 0.5, 24): posts y 1-4, boards 8 x 2.6 up to y 6.6, z 174 | TycoonCore.lua:75, 226-231; IpoServer.lua:21, 293-311 |
| What the rooms reach outside the floor | stage 1 dirt and weeds to x ± 35.5 and z 186.2; stage 5 skyline back to z 101 and up to y 29 | PlotArt.lua (measured by building every room, section 7) |
| VIP Lounge | floor 36 x 1 x 24 at (0, 0.5, 70); glass walls 10 high, 1 thick: **x -18.5 to 18.5, z 57.5 to 82.5**; door 8 wide in the front wall (z 82, **facing +Z, toward the plots' backs**); sign up to y 14.5; two seats inside | ShopServer.lua:35-38, 626-680 |
| The lounge door | the only `Touched` handler: a VIP walks through, anyone else gets the VIP prompt | ShopServer.lua:682-694 |
| Non-VIP inside the lounge | moved every 0.5 s to **(0, 4.5, 88)**, 6 studs in front of the door | ShopServer.lua:832-844 |
| Baseplate | **Studio fact:** 2048 x 16 x 2048 at (0, -8, 0): top y 0, x and z -1024 to 1024 | owner |
| SpawnLocation | **Studio fact:** 12 x 1 x 12 at (-1, 0.5, -1): x -7 to 5, z -7 to 5 | owner |
| Studio preview rooms | `Workspace.PREVIEW_STAGES`, rooms at x -600 + 70 (stage - 1), z 150: x -630 to -290, z 120 to 180 (Studio only, deleted before publishing) | docs/STUDIO_SYNC.md (preview block) |

So, from -Z to +Z: the spawn at the origin, the lounge at z 58-82 with its door toward the plots, the row of six plots at z 120-180 facing away from both, and empty grass after z 186.

## 2. How a player gets around today

- **Spawn to plot:** nobody walks it. The SpawnLocation drops the character at the origin, and `teleportToPlot` (TycoonCore.lua:833-838) moves it to its plot after 0.1 s, facing the front. Respawns do the same.
- **Plot to lounge:** the lounge is behind the plots. From plot 3 or 4 a player walks out of the open front (+Z), around the side of the plot, then about 100 studs back (-Z) to the lounge door, or straight through the back wall (room walls don't collide, PLOT_VISUALS.md). Nothing on the ground says where anything is.
- **The default camera** sits behind the player and looks +Z: out of the garage's open front, past the signs, at empty grass. **What lies in front of the plots is what players see most.**

## 3. StreamingEnabled

StreamingEnabled is on in the place. The client only keeps parts near the player: at least `StreamingMinRadius` (64 studs by default) and up to `StreamingTargetRadius` (1024 by default) while memory allows; the place's own values are not in the repo **(unverified)**. Parts farther away may never arrive on a low-memory phone, and may leave again as the player walks.

- **Small decor items** are each their own Model and the builder asks for `ModelStreamingMode = Atomic` (inside `pcall`): a lamp or a tree arrives whole, never a pole without its head.
- **Long strips are cut per plot block:** each street is one piece per plot spacing (about 90 studs), centered near its plot, so the piece under a player's feet is never one whose middle is 250 studs away. (How Roblox streams one part far longer than the radius is **unverified**; cutting costs 10 parts.)
- **The spawn plaza** only matters for the moment before the teleport and for players who walk back; on a phone it may stream out while the player is at the plots. Fine: nobody looks at it from there.
- **Far hills** may not be there on phones at all (they are 250+ studs away): they are an optional backdrop. `Model.LevelOfDetail = StreamingMesh` could show them as low-detail shapes when streamed out; left off for now **(unverified on phones)**.
- **The preview** (`PREVIEW_WORLD`) is shown whole in edit mode (no streaming there). In a playtest it streams like any other part.
- Not the world pass's change, but related: `teleportToPlot` moves the character without `RequestStreamAroundAsync`, so on a slow phone the plot can arrive a moment after the player (the Baseplate is under it either way) **(unverified)**.

## 4. The design

Bright chunky cartoon in PlotArt's palette: big simple Blocks, Balls and Cylinders, thick trim, no tiny detail. Every position below is a formula of the site (`PLOT_SPACING` S, the plot count N, the plot centers, the lounge, the spawn); the numbers are the defaults (S 90, N 6). "Gap lines" are halfway between plots plus one beyond each end: x = x1 - S/2 + k S, k = 0 ... N (-270, -180, -90, 0, 90, 180, 270).

| Element | Default geometry | Rule |
|---|---|---|
| **Spawn plaza** | a 44 x 44 square of warm stone around the pad (x -23 to 21, z -23 to 21), built as 4 slabs around a **bare 1 stud margin** around the pad; kerbs on its edge; 4 lit lamps at the corners, 3 benches, 4 round planters with flowers, a tree beyond each corner | centered on the pad (Studio fact); the pad and its margin stay empty, flat layers included |
| **Welcome arch** | two posts and a navy beam "BUILD YOUR STARTUP" in gold over the avenue's start (z 23) | text on both faces |
| **Avenue** | 8 wide, from the plaza (z 21) to a **cross walk** (z 32-40) 17.5 studs short of the lounge's back wall | x 0 (the lounge's axis) |
| **Lounge loop** | two **arms** (x ±23 to ±31) along both sides of the lounge, 4.5 studs from its walls, with a low hedge between arm and wall | from the lounge's numbers |
| **Lounge forecourt** | stone between the arms in front of the door (z 83-87), 2 lit lamps at its corners; the door's approach (x ±4) and the non-VIP drop spot (0, 88, radius 3) stay clear of anything taller than the paving | ShopServer's door and drop spot |
| **Back street** | 8 wide at z 87-95 behind the row, from the first gap line to the last; one piece per plot block | 5 studs short of what the rooms reach (z 100) |
| **Connectors** | 8 wide, z 95-191, through each gap line: between every two plots and around both ends | a gap is used only if it leaves 4 studs to each plot's reach; the two end ones always exist |
| **Front street** | 8 wide at z 191-199, the whole row; kerb on the far side; one piece per plot block | 1 stud past what the rooms and the building pass reach (z 190) |
| **Front walk** | per plot, 6 wide, from the floor's front edge (z 180) to the street | the only piece that enters the plot's front band; a flat layer 0.1 higher than the stage 1 dirt |
| **Street sign** | per plot, across the street (x center + 7, z 202): a post and a green board with the plot number on both faces | text = the slot number |
| **Lamps** | on the far side at every gap line (7, unlit: a glowing head only) | |
| **Trees and bushes** | 2 trees and 1 bush per plot on the far side; a row of trees on the lounge side of the back street, beyond the arms; 2 by the cross walk; 4 at the plaza | deterministic variants by index (3 sizes, 3 greens) |
| **Lawns** | a lighter lawn along the far side of the front street; a darker meadow on each side of the lounge loop | ground layer |
| **Low hills (optional)** | 6 wide, low spheres mostly buried: 4 in front (z 500-640), 1 on each side (x ±760); 18-26 studs high | 258+ studs from every other part at spacing 90 (221+ at 112), inside the Baseplate, away from the preview rooms |

Walking routes with it: spawn, plaza, under the arch, avenue, around the lounge by either arm, forecourt (the door), back street, any connector, front street, the plot's walk. The plot's number faces it across the street.

## 5. Rules (each one is a named check in `WorldVisuals.checks`)

- **Budget** (placeholders): at most **600 parts** and **8 lights** in the whole world. Built: **268 parts and 6 lights** at the default site; 151 (1 plot) to 268 (6 plots) at spacing 90 and 112. The lights are only the plaza's 4 and the forecourt's 2, whatever N is.
- **Decor never interferes:** every part anchored, `CanCollide`, `CanTouch` and `CanQuery` off, tiny and flat parts cast no shadow. Only the Baseplate (and the game's own floors) are solid: the paths are visual layers.
- **Layers:** ground tints top at y 0.04, paths at 0.16 (the stage 1 dirt is at 0.06), kerbs 0.4 tall. **Anti-z-fighting rule:** no two faces facing the same way may lie on the same plane and overlap, except bottoms resting on the ground (y 0, never seen). Path pieces only meet edge to edge, never overlap; different layers are at least 0.04 apart; nothing has its top at y 0 (the Baseplate's top).
- **Keep-outs:** no part enters a plot's floor, a plot's reach box (centre ± 36 across, from 50 behind to 40 in front, the front walk's flat strip excepted), a garage sign, the lounge (with a 0.5 margin), the door's approach, the drop spot, the spawn pad plus its 1 stud margin, or the Studio preview rooms (at the default site).
- **Nothing floats:** every part rests on the ground or on a chain of touching parts.
- **Inside the Baseplate:** every footprint (a hill's: its circle at ground level) stays inside x and z ±1024.
- **Connected:** the paths join the plaza around the spawn to every plot's front edge, edge to edge with at least 4 studs of contact.
- **Untouched:** the builder only creates parts in its own Model; the SpawnLocation, the Baseplate, the plot floors and the lounge are never moved, resized, renamed, re-parented or deleted.
- **Text:** only "BUILD YOUR STARTUP" and the plot numbers; no word about odds, chance, luck or randomness anywhere in the data (D9).
- **Palette:** every color is a palette key, every key defined (a sector can pass its own palette to `build`).
- **Materials:** SmoothPlastic, Plastic, Concrete, Cobblestone, Brick, Wood, WoodPlanks, Metal, Fabric, Grass, Neon (Neon only on parts named like a light).
- **Shapes:** Block, Ball, Cylinder (no Wedge: its slope can't be checked without Studio).

**Studio-only, not part of the pass:** the Baseplate's color (grass, docs/STUDIO_SYNC.md (b)), the Lighting values (ClockTime, Atmosphere, Bloom, ColorCorrection, same table) and `Workspace.StreamingEnabled` and its radii. The palette's lawn greens are picked to sit next to the Baseplate's (108, 172, 82).

## 6. Files and how it would be wired

- **`WorldArt.lua`** (ModuleScript, ServerScriptService): data only. `Site` (the copied script numbers and the Studio facts, each marked), `Layout` (widths, gaps, layers), `Palette`, `Pieces` (lamp, tree, bush, bench, planter, sign, arch: part lists around a base point), `Hills`, `Texts`, `Budget`.
- **`WorldVisuals.lua`** (ModuleScript, ServerScriptService): `site(art, spacing, count, centerOf)` (pure: the numbers of a site, from TycoonCore's real `plotCenter` when wired), `layout(art, site)` (pure: every path rectangle and decor placement), `build(parent, art, site, palette)` (the Model `World`), `validate(art)`, `checks(world, art, site)` (named checks, used by the tests and the preview), `check` (the flat list). No `GetService`, no `require`: art and site are passed in, so a broken module can't take another down.
- **Wiring (not applied):** TycoonCore requires both inside `pcall` (5 s wait, like PlotVisuals, TycoonCore.lua:56-61) and, once, before the PlayerAdded hook (TycoonCore.lua:840) builds the world with `pcall`, passing `PLOT_SPACING`, `MAX_PLOTS` and `plotCenter`: a spacing or count change moves the world with the plots, with no redesign. Exact edit: `docs/world_pass_integration.patch`.
- **Preview:** a command-bar block in `docs/STUDIO_SYNC_WORLD.md` builds `Workspace.PREVIEW_WORLD` (the world plus see-through ghosts where the plots and the lounge stand at runtime), prints one OK line per check, checks the two Studio facts against the real SpawnLocation and Baseplate (read only), and lists any hand-placed part it would overlap. Delete `PREVIEW_WORLD` before publishing.

## 7. Tests and what only Studio can judge

`tools/world_test.py` runs the real `WorldArt` and `WorldVisuals` in a fake Roblox (the plot visuals fake plus Workspace objects), and the real `PlotArt` and `PlotVisuals` to measure every room's reach. It checks every rule of section 5 for the default site and for a sweep of `PLOT_SPACING` 90 and 112 with 1 to 6 plots; compares every copied number with the real `TycoonCore.lua`, `IpoServer.lua` and `ShopServer.lua`; runs the preview block in the fake; and breaks the data and the builder on purpose: **65 mutation runs** (29 on the builder and the checks, 24 on the data and the copied numbers, 6 on the Studio sync blocks, 6 on the patch regeneration), each caught by its named check, never by a crash. It also runs the integration patch's two blocks, the Studio preview, cleanup and check blocks as written, and the patch's regeneration (`--regen-patch`). After the review fixes: 298 checks pass.

**Only the owner's eyes can judge:** the colors next to the real Baseplate under the place's Lighting, whether the street reads as a street from the default camera, the hills through the Atmosphere haze, the text size on the signs, how streaming looks on a real phone, and frame rate on a low-end phone.

## 8. Owner choices (defaults implemented; each is one value in `WorldArt`)

The arch and its words; street signs with the number only (no street name); hills on; lamps lit only at the plaza and the forecourt; the palette; the 1 stud bare margin around the spawn pad. Listed with the rest in docs/WORLD_ICONS_NOTES.md.
