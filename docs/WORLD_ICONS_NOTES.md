# World and icons pass: notes and progress

Branch `world-icons-pass` (from `main` at `e3c9e67`), worktree `../world-icons`. New files only; the one existing-file edit is the claim rows in `CONTRIBUTING.md`. No Studio, no MCP: everything here was written and tested outside Studio, with the free `luau` command-line tool and fake Roblox objects.

## Progress (the source of truth when this job is resumed)

Each item is one commit, pushed right after. An item is ticked in the same commit that does it.

**Phase 0: set-up**
- [x] 0.1 Claim every new file in `CONTRIBUTING.md`
- [x] 0.2 This notes file with the checklist

**Phase 1: shop UX (docs only)**
- [x] 1.1 `docs/SHOP_UX_PROPOSAL.md` (3,409 words; 6 open questions)

**Phase 2: world pass**
- [x] 2.1 `docs/WORLD_PASS_PROPOSAL.md` (2,481 words; numbers re-checked after the build in 2.4)
- [x] 2.2 `WorldArt.lua` (pure data)
- [x] 2.3 `WorldVisuals.lua` (builder, named checks, pure geometry)
- [x] 2.4 `tools/world_test.py` (fake Roblox, checks, parameter sweep): 213 checks (154 in Luau, 59 source checks)
- [x] 2.5 World mutants, group A: 29 runs on `WorldVisuals.lua` (builder breakages and weakened checks), 29 caught by their named checks
- [x] 2.6 World mutants, group B: 24 runs on `WorldArt.lua` (data rules, copied numbers, Studio facts); 53 in all, every one caught by its named check
- [x] 2.7 `docs/world_pass_integration.patch` (not applied): two blocks in TycoonCore (10 lines after line 61, 12 before line 840); `tools/world_test.py` runs both blocks in the fake and, with `--integration`, both suites on a patched copy
- [x] 2.8 World preview block (`Workspace.PREVIEW_WORLD`) in `docs/STUDIO_SYNC_WORLD.md`, run in a fake place by `tools/world_test.py` (23 checks)

**Phase 3: icons**
- [x] 3.1 `IconArt.lua` (pure data, style sheet): 38 recipes (6 Office props copied from PlotArt, 3 eggs, 12 creatures, 12 shop items, 5 HUD buttons)
- [x] 3.2 `IconVisuals.lua` (builders, pure size, framing and lazy-creation functions, the cache with the cap of 8, taps, named checks)
- [x] 3.3 `tools/icon_test.py`: 154 checks (97 in Luau, 57 source checks)
- [x] 3.4 Icon mutants, group A: 17 runs on `IconVisuals.lua` (style, light, framing, the cap plan, reuse, plates, taps, weakened checks), 17 caught by their named checks
- [x] 3.5 Icon mutants, group B: 17 runs on `IconArt.lua` (palette gaps, an emoji, a percent, a label on the clover, the grid, prop copies drifting from PlotArt, the cap, plates, rarity plates, light side, egg colors, keys, views, squashed circles, unknown creatures); 34 in all, every one caught by its named check
- [x] 3.6 Icon preview block (`StarterGui.PREVIEW_ICONS`) in `docs/STUDIO_SYNC_WORLD.md`, run in a fake place by `tools/icon_test.py` (16 checks)

**Phase 3b: previews (SVG text)**
- [x] 3b.1 `tools/render_previews.py` (standard library; `--check` says whether the SVGs match the data)
- [x] 3b.2 `docs/previews/world_topdown.svg` (an approximation: boxes seen from above)
- [x] 3b.3 `docs/previews/icons_sheet.svg` (an approximation: shapes and flat-shaded box faces)

**Phase 4: Studio sync and wrap-up**
- [x] 4.1 `docs/STUDIO_SYNC_WORLD.md` complete (files, SHA-256 and sizes, steps, hash block, previews, delete list, what to look at); `tools/world_test.py` runs its hash block on the real files
- [x] 4.2 These notes complete (judgment calls, OWNER CHOICE list, blocked items, risks, what was not tested, results)
- [x] 4.3 Release every claim in `CONTRIBUTING.md` (the 13 rows stay, set to free, like the design branches did)

**Phase 5: review fixes** (branch `world-icons-fix`, from `world-icons-pass` at `777f843`, worktree `../world-fix`, pushed to `world-icons-pass` after every commit)
- [x] 5.0 Claim the files touched in `CONTRIBUTING.md`
- [x] 5.1 Item 1: the permanent tests no longer read git history. The "only CONTRIBUTING.md differs" and "daily_test.py untouched" checks moved to `--review` (against the merge-base with `origin/main`); the patch test applies the patch to this worktree's `TycoonCore.lua` (exactly, then with fuzz `git apply -C1`), or, if the two marker lines are already there, checks that both blocks are in it exactly, once each, in the right places and order; a patch that does not apply fails the named check with "patch needs regenerating"
- [ ] 5.2 Item 2: one icon cap for the whole client
- [ ] 5.3 Item 3: the Studio previews' cleanup and check blocks
- [ ] 5.4 Item 4: SHOP_UX_PROPOSAL fixes
- [ ] 5.5 Item 5: the patch's hash and line numbers are for `e3c9e67` only; the regeneration is scripted and tested
- [ ] 5.6 Item 6: the top-down preview's labels
- [ ] 5.7 Item 7: minor notes (drift test, the cap is a guess, the light test)
- [ ] 5.8 Release the claims

## OWNER DEFAULT (decided by the owner for the review fixes)

1. **The ViewportFrame cap is global** across every window and every cache on the client.
2. **Direct `build()` calls** (the hero card, the details sheet) go through the same cap.
3. **"One window open at a time" alone is not enough** to keep the count down: the cap is enforced by the code.
4. **Shop order:** S1 builds the tutorial's Names and the "?" slot first, the tutorial uses them, and CUSTOMIZE PR 2 and PR 3 come after S1.
5. **S2 may edit the "Locked" check of `tools/daily_test.py`** in its own pull request, with a claim, and the test updated in the same pull request.
6. **Studio-only previews get a cleanup block and a check block.**

## Studio facts (measured by the owner, not in the repo)

These are placed by hand in Studio. They are treated as fixed constants in `WorldArt.Site` (marked "Studio fact") and the tests use them as they are; nothing parses them from a `.lua` file because no script creates these two objects.

| Object | Size | Position | What follows |
|---|---|---|---|
| `Workspace.Baseplate` | 2048 x 16 x 2048 | (0, -8, 0) | its top is y = 0, it spans x and z from -1024 to 1024 |
| `Workspace.SpawnLocation` | 12 x 1 x 12 | (-1, 0.5, -1) | the pad covers x -7 to 5, z -7 to 5, y 0 to 1 |

The world builder never moves, resizes, replaces or deletes either of them, and nothing it builds covers the spawn pad. The Studio preview block reads both objects (read only) and prints whether they still match these numbers.

## Judgment calls

- **Shop proposal (phase 1):** the phone numbers use a 36 px Roblox top bar (GUI 667 x 339 and 320 x 532), the same assumption as TUTORIAL_PROPOSAL section 3; portrait's window is capped at 470 px tall, so the shop looks the same with a 0 px bar. Text widths (characters per line) are marked as estimates.
- **Shop proposal:** its future tests go in a new `tools/shop_ux_test.py`, not in `tools/daily_test.py` (other branches own that file).
- **Shop proposal:** Robux buys keep Roblox's own prompt as their only confirmation; the two-tap confirm is proposed for Cash buys above a threshold (open question 2).
- **World: the plots' reach.** The world keeps out of a box around each plot (36 studs to the sides, 50 behind, 40 in front of the center, 32 up), not just the 60 x 60 floor: today's rooms reach 35.5 to the sides (stage 1's dirt), 49 behind (stage 5's skyline) and 36.2 in front (stage 1's dirt), and the building pass (branch `building-pass`, not merged) puts ground pieces up to 40 in front. `tools/world_test.py` builds all five rooms and fails if one reaches past the box.
- **World: the front walks** are the only pieces that enter a plot's box: a flat strip from the floor's front edge to the front street, 0.1 stud above stage 1's yard dirt (so the two never flicker). If the building pass lands, its doorstep path lies under the walk's first studs.
- **World: the Studio preview rooms** (`PREVIEW_STAGES`, x -630 to -290) are a keep-out only at spacing 90: they were placed for it. At spacing 112 plot 1 itself would stand on them, so the preview snippet in docs/STUDIO_SYNC.md would have to move (to about x -700) first.
- **World: font.** The arch uses `FredokaOne`, not PlotArt's `LuckiestGuy`: the rule against the four odds words in strings also catches that font's name.
- **World: a missing palette color** builds bright magenta instead of stopping the build (a sector palette with a gap still gives a world); the `palette` check names the gap.
- **World preview:** it requires a clone of each ModuleScript, so a module pasted a moment ago is used even if the command bar required the old one before (WorldArt and WorldVisuals require nothing themselves, so a clone works alone). It stops at once with a message if the two ModuleScripts don't exist, instead of waiting forever.
- **Icons: the Office props are copied.** `IconArt.Models` holds the six PlotArt props part for part (at their drawn size: PlotArt scales them by 1.2 to 1.5 for the room). PlotArt lives in ServerScriptService, which the client can't read, and moving it is an edit to an existing file. `tools/icon_test.py` fails if a copy drifts from PlotArt (names, shapes, sizes and offsets up to the scale, colors, materials, turns). Texts (BIG IDEAS, STARTUP) and the coffee steam are left out: a ViewportFrame draws neither SurfaceGuis nor particles.
- **Icons: creature models use CreatureModels' sphere meshes.** `CreatureModels.build` stretches round parts with a `SpecialMesh` of type Sphere (built in, no mesh or texture file). That is the only mesh object any icon contains; the `assets` check allows it only in creature icons, with no `MeshId` or `TextureId`.
- **Icons: eggs are drawn shapes, not 3D.** A Ball part is always round, so a 3D egg would need a SpecialMesh; an outlined, shaded oval reads as an egg at 56 px and costs no ViewportFrame.
- **Icons: the clover recipe's key.** Icons are looked up by the ShopConfig key, so the clover's recipe sits under that product's key, written as a Lua field name (never a quoted string); the recipe is named `Clover`, which is what an instance or a preview caption shows. No quoted string in the four new Lua files contains the words random, chance, odds or luck (`tools/world_test.py` and `tools/icon_test.py` check every string literal).
- **Icons: the HUD magnet is white.** The first render of the icon sheet showed the red magnet almost vanishing on the red-orange POACH button (232, 72, 62 on 225, 95, 60). It is now white with soft gray tips, like the other HUD icons; the preview block and the sheet show every HUD icon on its real button color so this can be judged.
- **Icons: the cap is 8 live ViewportFrames.** The shop shows at most 3 to 4 cards at once on a phone (242 px of page in landscape, 350 in portrait, section 3.10 of the shop proposal), plus one 72 px hero icon and the details sheet: 6 at most on screen. 8 leaves room to scroll back and forth without rebuilding, and a ViewportFrame off screen is kept out of the game tree (it draws nothing). Past the cap a card shows its plate until a model can be dropped (least recently seen first).
- **World: decor streaming.** Each decor item is its own Model with `ModelStreamingMode = Atomic`, set inside `pcall` (if a Roblox version refuses it from a script, the item keeps the default). The two streets are cut into one piece per plot block, so the piece under a player is never centered far away.
- **World: the real objects in the tests.** `tools/world_test.py` doesn't trust copies for the plots and the lounge: it runs `plotCenter` and `makePart` cut from `TycoonCore.lua` and `buildVipLounge` cut from `ShopServer.lua` in its fake, builds the world next to them, and checks that none of them moved and that no world part goes into them. The copied numbers in `WorldArt.Site` are also compared one by one with the scripts.
- **World: "never solid beyond the Baseplate"** is read as: no world part is solid at all (CanCollide, CanTouch, CanQuery off), and every footprint stays inside the Baseplate's 2048 x 2048. The far hills are big spheres sunk into the ground (their caps are 18 to 26 studs high); the hidden part goes far below the Baseplate, which is harmless because nothing is solid and nobody sees under the ground.
- **World: lights.** Six PointLights (the plaza's four lamps and the forecourt's two), whatever the plot count; every other lamp only has a glowing Neon lantern. Budget 8.
- **World and icons: only plain Parts.** A WedgePart, MeshPart or Union fails the checks (a Wedge's slope can't be checked without Studio, and reading `Shape` on a MeshPart errors in Roblox).
- **Tests: the odds words.** The four words appear in the test files only as test inputs (the checks that forbid them, and the mutants that must be caught). The rule is applied to every quoted string of the four new Lua files, to every text the world or an icon shows, and to the recipe names and captions.

## OWNER CHOICE

Defaults picked where the owner's taste decides. Each is implemented; the place to change it is given.

**World** (`WorldArt.lua` unless said otherwise)
1. **The welcome arch** over the avenue, BUILD YOUR STARTUP in gold on navy, both faces (`Pieces.Arch`; the item `WelcomeArch` in `WorldVisuals.layout` places it).
2. **Street signs show the plot number only** (1 to 6), no street name, across the street facing the plot (`Pieces.Sign`; `Layout.signDX`, `signDZ`).
3. **Six far hills** as a horizon (`Hills`; empty the list for none).
4. **Lit lamps only at the plaza and the forecourt** (six PointLights); the street lamps only glow (`LampLight`, and `lit = true` in `WorldVisuals.layout`).
5. **The palette**: warm stone plaza, sand paths, blue-gray streets, white kerbs, two lawn greens next to the Baseplate's (108, 172, 82), three tree greens (`Palette`; a sector can pass its own palette to `build`).
6. **A 1 stud ring of bare grass** around the spawn pad, inside the plaza (`Layout.spawnMargin`): it also protects the pad if the measured position is a little off.
7. **SmoothPlastic paths and Concrete kerbs** (in `WorldVisuals.build`): no texture seams where path pieces meet.
8. **Widths:** paths and streets 8, plot walks 6 (`Layout.pathWidth`, `walkWidth`); the front street 1 stud past what the plots reach (`frontGap`).
9. **Trees:** three sizes and greens in turn, 2 per plot across the street, a row behind the back street, 4 round the plaza, 2 by the cross walk (`Pieces.TreeA` to `TreeC`, `Layout.treeDX` and friends).

**Icons** (`IconArt.lua`)
10. **A four-leaf clover for the Luck Boost product** (the same idea as the old emoji, with no text at all). Alternative: an egg with a small sparkle.
11. **The only icon texts are 2x, +3 and $** (`Texts`): the 2x Cash coin, the Extra Slots badge, the Cash bill and bag.
12. **HUD drawings:** an egg (EGGS), a shopping bag (SHOP), two people (TEAM), a magnet (POACH: it pulls employees over), a rising bar chart with an arrow (IPO); light figures on the colored buttons (`Hud`).
13. **Plates:** cream under shop, egg and Office icons; creatures on a plate tinted by their rarity (`RarityPlates`).
14. **3D views:** the Office props from the front-left and a little above (`PROP_VIEW`, yaw -28, pitch 22); creatures from the front, a little to one side (`CREATURE_VIEW`).
15. **The cap of 8 live ViewportFrames** (`Style.viewportCap`), and the outline 4 grid units wide (`Style.outline`: 2 px at 56, 3 px at 72).

**Shop** (`docs/SHOP_UX_PROPOSAL.md`, section 7): six open questions, most important first: the landscape tab rail, confirming Cash buys, showing the locked rungs, badges, 3D or drawn icons on phones, the details sheet.

## Blocked

Nothing was blocked. No file this job needed was claimed by someone else (the Ownership table and every remote branch were checked on 2026-10-06), and every phase was finished.

## Risks

1. **Nothing is wired in yet.** The world needs the TycoonCore edit (`docs/world_pass_integration.patch`, owner's approval); the icons need the shop pull requests (`docs/SHOP_UX_PROPOSAL.md` section 5). Until then the four modules do nothing in the game.
2. **StreamingEnabled (unverified):** on a low-memory phone, parts beyond the minimum radius (64 studs by default) may stream out: the far hills and the plaza will often be missing there, and how Roblox streams very long parts is not documented here (the streets are cut per plot block for that reason). Related, and not this pass's change: `teleportToPlot` moves the character without `RequestStreamAroundAsync`.
3. **Copied numbers can drift.** `WorldArt.Site` copies numbers from TycoonCore, IpoServer and ShopServer, and `IconArt.Models` copies PlotArt's six props. The tests fail when a copy differs, so whoever changes those scripts must update the copies in the same pull request.
4. **Bigger buildings later.** The building pass (branch `building-pass`) lays its doorstep path under the plot walks (no flicker: different heights). CUSTOMIZE's 78 x 82 buildings would reach x ±41.3 and back to z 94: at spacing 90 the connectors between plots would drop out by the layout's own rule (the two end ones stay, so every plot is still reached), and the back street (z 87-95) would have to move toward the lounge. Raising `Site.plotReach` makes the tests say exactly that.
5. **The Studio preview rooms** (`PREVIEW_STAGES`) only fit spacing 90: at 112 plot 1 would stand on them, so their snippet must move before a spacing change.
6. **Phones and ViewportFrames:** the cap of 8 is a reasoned guess, not a measurement. ViewportFrames cost the most on low-end phones; lower `Style.viewportCap` if a phone test says so (the cache keeps working: more cards show their plate while they wait).
7. **The fake is not Roblox.** Materials, Neon and Bloom, the haze, SurfaceGui text size, UICorner on turned frames, UIStroke and UIGradient looks, and the ViewportFrame's ambient light are only approximated or not modelled at all. The two SVG previews are approximations too.
8. **Command-bar `require` of a clone.** The preview blocks require `module:Clone()` so a freshly pasted module is used. This is a common Studio habit but was not run in Studio here; if it ever fails, require the module itself and reopen the place after each paste.

## What was not tested (no Studio, no device)

- Nothing ran in Roblox Studio, in a live server or on a phone; the Studio MCP was not used.
- How anything looks: colors next to the real Baseplate under the place's Lighting, materials, Neon glow, the hills in the haze, text sizes, the icons at 56 px on a real screen, contrast on the HUD buttons.
- StreamingEnabled behavior, frame rate and memory on phones, and the cost of the SurfaceGuis (14 in the world).
- `ModelStreamingMode = Atomic` set from a server script (inside `pcall`), and requiring a cloned ModuleScript from the command bar.
- The integration patch in a running game: only in the fake (both modules, one missing, broken data) and with `tools/daily_test.py` and `tools/world_test.py` on a patched copy.
- The shop redesign: a proposal only, no code; its phone numbers come from the code, its text widths are estimates.
- Tap animations in a real frame loop (the fake runs them step by step).

## Results (final)

| Suite | Checks | Mutation runs |
|---|---|---|
| `tools/daily_test.py` (other branches own it; unchanged) | 1,772 pass (1,740 before, plus 32 per-file scans of the four new files), 0 failed | 20 of 20 (its own) |
| `tools/world_test.py` | 275 pass, 0 failed (155 world program, 59 source, 23 world preview, 6 hash block, 9 sync table, 7 integration blocks, 16 patch source) | 53 of 53, each caught by its named check (29 builder and checks, 24 data) |
| `tools/icon_test.py` | 174 pass, 0 failed (101 icon program, 16 icon preview, 57 source) | 34 of 34, each caught by its named check (17 builder and checks, 17 data) |

- **World:** 268 parts and 6 lights at the default site (budgets 600 and 8); the sweep (spacing 90 and 112, 1 to 6 plots) gives 151 to 268 parts and always 6 lights, every named check passing.
- **Icons:** 38 recipes; 18 3D icons of 9 parts (Pixel Pigeon) to 24 (Desk, Server Rack); 20 drawn icons of 3 shapes (HUD bag) to 10 (crown); at most 8 ViewportFrames alive while a list scrolls (measured: the peak is exactly 8).
- **Files:** `WorldArt.lua` 13,042 bytes, `WorldVisuals.lua` 48,782, `IconArt.lua` 30,143, `IconVisuals.lua` 37,198 (SHA-256 in docs/STUDIO_SYNC_WORLD.md, checked by `tools/world_test.py`).
