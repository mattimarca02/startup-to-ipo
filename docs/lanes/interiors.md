# Lane: interiors

Only the interiors lane edits this file. See docs/LANES.md.

## Backlog (in order)

The furniture inside the 60 x 60 room, different at each funding stage, from the 3D kit (`ReplicatedStorage.KitModels`, docs/KIT_MODELS.md) recolored per stage, with a Parts version of every kit piece for when the kit is missing. No new models. Every PlotArt rule stays: gameplay positions and reserved zones, the six upgrade props unchanged, at most 260 parts and 3 PointLights per room (with the kit and without it), no odds text. Fingerprints change only on purpose and the PR says so.

1. **Kit furniture builder + the Garage (stage 1).** PlotVisuals builds "kit pieces" (a kit key, a spot, a quarter turn, a scale, a color and material per role) from KitModels, with the Parts fallback from `PlotArt.Kit`; validate and check cover them. The Garage gets: crates as hire desks (kit `Crate`), a workbench (`Workbench`), an old desk and chair for the founder (`Desk`, `Chair`, worn colors), the bare bulb (`BareBulb`). Stage 1 fingerprint updated on purpose.
2. **Small Office (stage 2, Seed).** Hire desks from the kit `Desk` with a `Computer` on each (scaled to the desk zone; no chairs for hires: a chair would stand where the hire stands), the founder's desk and chair from the kit, a kit `Plant` or two, mint/oak recolors.
3. **Big Office (stage 3, Series A).** As stage 2 plus a `MeetingTable` with chairs and a `Whiteboard`, brick-loft recolors.
4. **Small Corporate (stage 4, Series B).** Dark wood and gold recolors, `Laptop` instead of `Computer` on the hire desks, a `BoardTable` with chairs, `Shelf`, `Plant`.
5. **Big Corporate (stage 5, IPO-ready).** The same dark wood and gold, `Laptop`s, the `BoardTable`, `Armchair`s and a `Rug` in the lounge, `ReceptionDesk` if it fits outside every zone.
6. **Studio preview and checks.** A command-bar snippet (in this lane's Studio steps) that builds the five rooms with the kit next to each other, and a kit check of the furniture keys the rooms use.

## Doing now

waiting for review of PR #40

## Last PR

#40 `interiors-kit-garage` (backlog item 1), open, waiting for review.

## Last report

The rooms can now use furniture from the 3D kit. PlotVisuals copies a kit model's MeshParts, fits them to the kit size, scales and turns them, recolors each by its role, and builds the same piece from Parts when the kit or a model is missing or can't be used. It finds ReplicatedStorage.KitModels by itself, so TycoonCore does not change. The Garage got kit crates as hire desks, an old desk and chair, a workbench, a pile of crates and the kit's bare bulb. Its fingerprint was taken again on purpose; the six props and the layout did not change. Stage 1 has 258 parts with the kit and 260 from Parts (budget 260). daily_test passes: the plot visuals check is 456 passed, the new kit mutation runner caught 13 of 13, wiring is 80 passed. hud, world, icon, shop_ux and building all pass. lobby_test fails only its 4 known "Lobby all" doc pins for PlotVisuals (the same as R1/B1). Pushing straight to main was refused by this session's permission check, so my claim rows and this file are inside PR #40. Waiting for the owner: merge (or let the lane push lane files to main).

## Requests to other lanes

- **I1, to gameplay (tools/lobby_test.py):** the same as the ux lane's R1 and the building lane's B1. PR #40 changes PlotVisuals.lua (new sha256 `8eefee60866bb2ef0a31cbeda361e5f4bd145844d27644dd054e9e5951d8fcca`, 41197 bytes), so lobby_test's 4 "Lobby all" pins of docs/STUDIO_SYNC_LOBBY.md fail. Please check that section as history.
- **I2, to quality (CLAUDE.md, after #40 merges):** in "Plot visuals", replace "built-in Parts and the allowed materials only, no assets" with: built-in Parts, plus furniture from the 3D kit in ReplicatedStorage.KitModels, recolored per stage, with a Parts version of every kit piece (PlotArt.Kit). PlotVisuals reads only that one service (findKit, inside pcall). Every room rule holds with the kit and without it.

## Studio steps (merged PRs not yet in Studio)

PR #40 (once merged): paste these two ModuleScripts in ServerScriptService.

| Script | sha256 | Bytes |
|---|---|---|
| `PlotArt` | `e1d3f7e0e6dd789c3d4a7135a474e8dc92eacdfb23d9c65fcc0599ea9dd2b0c6` | 63975 |
| `PlotVisuals` | `8eefee60866bb2ef0a31cbeda361e5f4bd145844d27644dd054e9e5951d8fcca` | 41197 |

Playtest (F5): your garage and the free garages show kit crates as hire desks, the old desk and chair with the PC, the workbench, the crates in the back-right corner, and the glowing bulb. Output must have no "Plot visuals:" warning (a warning names a kit model built from Parts instead). Optional preview in the command bar (delete PREVIEW_STAGES before publishing):

```lua
local SSS = game:GetService("ServerScriptService")
local PlotArt, PlotVisuals = require(SSS.PlotArt), require(SSS.PlotVisuals)
local kit = PlotVisuals.findKit(PlotArt)
local old = workspace:FindFirstChild("PREVIEW_STAGES") if old then old:Destroy() end
local folder = Instance.new("Folder") folder.Name = "PREVIEW_STAGES" folder.Parent = workspace
for stage = 1, #PlotArt.Stages do
	local center = Vector3.new(-600 + (stage - 1) * 70, 0.5, 150)
	local floor = Instance.new("Part") floor.Name = "Floor" floor.Anchored = true floor.Size = Vector3.new(60, 1, 60) floor.Position = center floor.Parent = folder
	PlotVisuals.styleFloor(floor, PlotArt, stage)
	local room = PlotVisuals.buildRoom(folder, center, PlotArt, stage, kit)
	for _, slot in ipairs(PlotArt.Layout.itemSlots) do PlotVisuals.buildProp(room.UpgradeProps, center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z)) end
	local meshes = 0 for _, d in ipairs(room:GetDescendants()) do if d:IsA("MeshPart") then meshes += 1 end end
	local problems = PlotVisuals.check(room, center, PlotArt)
	print("Stage", stage, #problems == 0 and "OK" or problems[1], "kit MeshParts:", meshes, "kit found:", kit ~= nil)
end
```
Stage 1 should print OK with 39 kit MeshParts.
