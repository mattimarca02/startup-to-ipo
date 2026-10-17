# Studio sync for the building pass (addendum to docs/STUDIO_SYNC.md)

> **Built differently in lobby L2 (2026-10-16, branch `lobby-all`).** This pass's maths, inside check and fade client were kept (BuildingClient is now at the repo root and works in each garage's turned frame). Its Parts-only, never-solid shell was replaced by the five kit buildings with invisible solid walls (docs/PLOT_VISUALS.md, "The building"; docs/LOBBY_ALL_PROGRESS.md). The integration patch is not applied: L2 wired TycoonCore by hand (two of its three edits). The Studio steps are in docs/STUDIO_SYNC_LOBBY.md, not in docs/STUDIO_SYNC_BUILDING.md.

Branch `building-pass` (from `visuals-garage` at `7f5c141`). Nothing here touches Roblox: it is the list of what the Mac has to do, in order. `docs/STUDIO_SYNC.md` still describes everything of `visuals-garage`; this file adds only the building pass. The design is in `docs/BUILDING_PASS_PROPOSAL.md`.

The pass has two halves, and you can do the first without approving the second:

- **Half A, new scripts only** (steps 1 to 3): three new scripts and the preview. **Nothing calls them yet**, so the game plays exactly as before. You can look at the five buildings in the preview and test the roof fade by walking into them.
- **Half B, the hook** (step 5, after you approve `docs/building_pass_integration.patch`): the changed `TycoonCore`, which builds the building around every player's room.

## (a) Files to copy

SHA-256 and size in bytes of each file as it is in the repo (`\n` line endings, one final newline; Studio may add or drop that final newline, so the check below accepts both).

| Script | Studio type and place | Source file in the repo | State | sha256 | Bytes |
|---|---|---|---|---|---|
| `PlotBuilding` | ModuleScript, ServerScriptService | `PlotBuilding.lua` | new | `d9125276e65b9e14b254cebad94de74c0de1077dc570b77a97a9251a8622d00b` | 28785 |
| `PlotBuildingVisuals` | ModuleScript, ServerScriptService | `PlotBuildingVisuals.lua` | new | `81aa04fc16e68882e31a688f19963b9d4a4292e3534d8326c3c9ecf14c1b9236` | 22886 |
| `BuildingClient` | LocalScript, StarterPlayer > StarterPlayerScripts | `docs/studio_scripts/BuildingClient.lua` (**not** at the repo root, on purpose) | new | `f75c4590367a696bfac59af79799d4735ff84ca32e240c41461acb1155ba681f` | 8981 |
| `TycoonCore` (half B only) | Script, ServerScriptService | `TycoonCore.lua` after `git apply docs/building_pass_integration.patch` | changed | `75aafd603a293524217fead0bea993303b4ede32800075f915311f0a86c3af1c` | 35552 |

`TycoonCore` today (`visuals-garage` and this branch, the patch is **not** applied in the repo yet) is `77ce9c43dcbd03ae5e03e5e112c99b3763af7b92e6527a367e3eeee112e61aa9`, 34330 bytes, the same as in `docs/STUDIO_SYNC.md`. The patch itself (`docs/building_pass_integration.patch`) is `a6000b68a6aeb1160575260ba49a1fb01af55bb0f280c41336e2d2cdbf2de6e8`, 2396 bytes. Every other script is unchanged.

Studio-only settings: **none new.** The building pass changes no Lighting, Atmosphere, Bloom or Baseplate setting, adds no remote, no save section and no setting. Its parts cast no shadow and it adds no lights.

## (b) Steps on the Mac

1. **Pull.** In a terminal in the project folder: `git fetch origin building-pass`, `git checkout building-pass`, `git pull origin building-pass`. `git log --oneline -1` must show the newest commit of this branch.
2. **Create the scripts by hand** (they don't exist in Studio yet):
   - In **ServerScriptService**: two new **ModuleScripts**, named exactly `PlotBuilding` and `PlotBuildingVisuals`. For each: open the `.lua` file of the same name in the repo root, select all, copy; in Studio double-click the script, select all, paste.
   - In **StarterPlayer > StarterPlayerScripts**: a new, empty **LocalScript** named exactly `BuildingClient`. Open `docs/studio_scripts/BuildingClient.lua`, select all, copy; double-click the LocalScript, select all, paste. (A `Script` or a `ModuleScript` will not work: it must be a LocalScript.)
   - **View > Drafts**: commit every draft.
3. **Verify the hashes and look at the preview.** Paste the hash block (below) into the **command bar** (View > Command Bar) and press Enter: every line must say `OK`. Then paste the preview block: it prints `Stage n OK` for each of the five buildings, or the first problem. At this point the game itself is unchanged and nothing has been published.
4. **Playtest the roof fade in the preview** (checklist in section (c)). This is the half you can test completely before approving anything.
5. **Half B, after you approve the integration edits:** in the repo, on the branch, run `git apply docs/building_pass_integration.patch` (it changes only `TycoonCore.lua`; run both test files first). Copy the patched `TycoonCore.lua` into the `TycoonCore` Script in Studio (select all, paste), commit the draft, and check the hash again (it must say `OK (building hook)`). Playtest again (section (c), second list). Create the three new scripts **before** pasting `TycoonCore`: it waits 5 seconds for them inside `pcall`, so it never hangs, but without them the building is missing and the Output says `Plot buildings are off`.
6. **Delete `Workspace.PREVIEW_STAGES` before publishing** (select it in the Explorer, press Delete). Then publish with **Shut down all servers** (docs/PUBLISH_RULES.md). The building pass adds no save section and no remote, so the rollback floor is unchanged.

### Hash check (command bar)

```lua
local K = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
	0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
	0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
	0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
	0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
}
local function sha256(msg)
	local h = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 }
	local len = #msg
	msg ..= "\128" .. string.rep("\0", (55 - len) % 64) .. string.pack(">I8", len * 8)
	local w = {}
	for chunk = 1, #msg, 64 do
		for i = 0, 15 do w[i] = string.unpack(">I4", msg, chunk + i * 4) end
		for i = 16, 63 do
			local a, b = w[i - 15], w[i - 2]
			local s0 = bit32.bxor(bit32.rrotate(a, 7), bit32.rrotate(a, 18), bit32.rshift(a, 3))
			local s1 = bit32.bxor(bit32.rrotate(b, 17), bit32.rrotate(b, 19), bit32.rshift(b, 10))
			w[i] = (w[i - 16] + s0 + w[i - 7] + s1) % 2 ^ 32
		end
		local a, b, c, d, e, f, g, hh = table.unpack(h)
		for i = 0, 63 do
			local S1 = bit32.bxor(bit32.rrotate(e, 6), bit32.rrotate(e, 11), bit32.rrotate(e, 25))
			local ch = bit32.bxor(bit32.band(e, f), bit32.band(bit32.bnot(e), g))
			local t1 = (hh + S1 + ch + K[i + 1] + w[i]) % 2 ^ 32
			local S0 = bit32.bxor(bit32.rrotate(a, 2), bit32.rrotate(a, 13), bit32.rrotate(a, 22))
			local maj = bit32.bxor(bit32.band(a, b), bit32.band(a, c), bit32.band(b, c))
			local t2 = (S0 + maj) % 2 ^ 32
			hh, g, f, e, d, c, b, a = g, f, e, (d + t1) % 2 ^ 32, c, b, a, (t1 + t2) % 2 ^ 32
		end
		local r = { a, b, c, d, e, f, g, hh }
		for i = 1, 8 do h[i] = (h[i] + r[i]) % 2 ^ 32 end
	end
	local out = {}
	for i = 1, 8 do out[i] = string.format("%08x", h[i]) end
	return table.concat(out)
end

local SSS = game:GetService("ServerScriptService")
local SPS = game:GetService("StarterPlayer"):WaitForChild("StarterPlayerScripts")
-- Each script may have more than one accepted hash (TycoonCore: without or with the building hook)
local WANT = {
	PlotBuilding = { { "d9125276e65b9e14b254cebad94de74c0de1077dc570b77a97a9251a8622d00b", 28785, "" } },
	PlotBuildingVisuals = { { "81aa04fc16e68882e31a688f19963b9d4a4292e3534d8326c3c9ecf14c1b9236", 22886, "" } },
	BuildingClient = { { "f75c4590367a696bfac59af79799d4735ff84ca32e240c41461acb1155ba681f", 8981, "" } },
	TycoonCore = {
		{ "77ce9c43dcbd03ae5e03e5e112c99b3763af7b92e6527a367e3eeee112e61aa9", 34330, "(no building hook yet: half A)" },
		{ "75aafd603a293524217fead0bea993303b4ede32800075f915311f0a86c3af1c", 35552, "(building hook)" },
	},
}
for name, accepted in pairs(WANT) do
	local script = SSS:FindFirstChild(name) or SPS:FindFirstChild(name)
	if not script then
		print(name, "MISSING (create it)")
	else
		local source = script.Source
		local verdict = "DIFFERENT"
		for _, want in ipairs(accepted) do
			local same = sha256(source) == want[1] and #source == want[2]
			local withNewline = sha256(source .. "\n") == want[1] and #source + 1 == want[2]
			if same or withNewline then verdict = "OK " .. want[3] end
		end
		print(name, script.ClassName, verdict, #source, "bytes")
	end
end
```

A line that says `DIFFERENT` names the script to paste again. `BuildingClient` must say `LocalScript`.

### Rebuild the preview (command bar): the five rooms with their buildings

Run it from edit mode (no playtest). It rebuilds `Workspace.PREVIEW_STAGES` (the rooms side by side at x = -600, 70 apart, each with its six props and now its building) and checks every room and every building.

```lua
local SSS = game:GetService("ServerScriptService")
local PlotArt = require(SSS.PlotArt)
local PlotVisuals = require(SSS.PlotVisuals)
local PlotBuilding = require(SSS.PlotBuilding)
local PlotBuildingVisuals = require(SSS.PlotBuildingVisuals)
local old = workspace:FindFirstChild("PREVIEW_STAGES")
if old then old:Destroy() end
local folder = Instance.new("Folder")
folder.Name = "PREVIEW_STAGES"
folder.Parent = workspace
local zones = PlotVisuals.zones(PlotArt.Layout)
for stage = 1, #PlotArt.Stages do
	local center = Vector3.new(-600 + (stage - 1) * 70, 0.5, 150)
	local floor = Instance.new("Part")
	floor.Name = "Floor"
	floor.Anchored = true
	floor.Size = Vector3.new(60, 1, 60)
	floor.Position = center
	floor.Parent = folder
	PlotVisuals.styleFloor(floor, PlotArt, stage)
	local room = PlotVisuals.buildRoom(folder, center, PlotArt, stage)
	for _, slot in ipairs(PlotArt.Layout.itemSlots) do
		PlotVisuals.buildProp(room.UpgradeProps, center, PlotArt, slot.name, Vector3.new(slot.x, 0, slot.z))
	end
	local building = PlotBuildingVisuals.build(folder, center, PlotArt, PlotBuilding, stage)
	local roomProblems = PlotVisuals.check(room, center, PlotArt)
	local buildingProblems = PlotBuildingVisuals.check(building, center, PlotArt, PlotBuilding, { zones = zones })
	print("Stage", stage, #roomProblems == 0 and "room OK" or roomProblems[1], #buildingProblems == 0 and "building OK" or buildingProblems[1])
end
```

The preview buildings are tagged and carry their numbers like the real ones, so `BuildingClient` fades them in a playtest.

To stand inside preview stage `n` in a **playtest** (F5), run this in the command bar while playing (if the character doesn't move, switch the context dropdown in the Output window to **Server** and run it again):

```lua
local n = 3 -- 1 to 5
local player = game:GetService("Players"):GetPlayers()[1]
player.Character:PivotTo(CFrame.new(-600 + (n - 1) * 70, 6, 150 + 12)) -- inside, the roof should fade
-- player.Character:PivotTo(CFrame.new(-600 + (n - 1) * 70, 6, 150 + 40)) -- in front of the door, outside, the roof is solid
```

## (c) What to look at by hand (nothing of this could be checked without Studio)

Half A, in the preview (the five rooms at x = -600, in a playtest):

1. **Outside look.** Walk around each of the five buildings: bright, chunky, readable? Is the door clearly a door (9 wide, 9 high), the windows windows, the roof a roof? Does stage 1 look like a rusty garage with a board on the roof, stage 5 like a headquarters?
2. **The roof fade.** Walk in through the door: the front wall should start to fade when you are about 3.5 studs from it, and the roof and every wall should be gone about 0.4 seconds later, leaving the open room as it is today. Walk out: everything comes back to exactly what it was (glass stays glass). Stand on a wall line and step back and forth: no flicker.
3. **Text.** The `OFFICE` / `HQ` / `BUILD YOUR STARTUP` signs are on the **front** and readable from the front (the code assumes `NormalId.Back` is the +Z face, as `PlotVisuals` does), and they disappear with the wall (no floating letters).
4. **Nothing in the way.** You can walk through the walls and the roof, your camera is never pushed in by a wall, clicks and the shop buttons work through them (nothing is solid or hit by a ray).
5. **Phone.** Test > Device (320x568 and 667x375): the fade does not depend on the screen, but look at the frame rate in the playtest stats while the roof fades.
6. **The lighting.** With the roof closed, is the building too dark or too bright against the grass? The building casts no shadow on the room by design; with the roof gone the room is lit exactly as today.

Half B (the hook), in a normal playtest:

7. Join as a new player: the Garage building is there when you spawn (inside the building, roof already faded, no flash of a closed roof).
8. Buy the six upgrades in the shop's Office tab: nothing about the building changes, the props pop in as before.
9. Debug tab: raise the valuation so the funding stage changes while you stand inside: the room flashes and swaps as before, the new building appears around it already faded, the roof never shuts while you are inside.
10. Go public (IPO): back to the Garage building. Output window: no red text, no `Plot buildings are off`, no `Plot visuals: building failed`.
11. A second player (Test > Clients and Servers, 2 players): each sees the other's building solid from outside; walking into the other's plot fades that plot's roof for the walker only.

## (d) Taking it out again

Half B is one patch: copy the old `TycoonCore` back (`git show 7f5c141:TycoonCore.lua`, hash `77ce9c43...`). Half A: delete the three scripts and `Workspace.PREVIEW_STAGES`. Nothing was saved, so no player data is affected either way.
