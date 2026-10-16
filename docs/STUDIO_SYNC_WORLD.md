# Studio sync: the world and icons pass

> **Lobby-all (2026-10-16):** `WorldArt` and `WorldVisuals` changed on branch `lobby-all` (the ring around the plaza, lobby L4). The rows and the hash block below give their current files. TycoonCore now builds the ring world itself when `LobbyConfig.ClaimEnabled` is on; the row patch (docs/world_pass_integration.patch) is superseded and never applied. The full list for that branch is docs/STUDIO_SYNC_LOBBY.md, section "Lobby all".

Branch `world-icons-pass` (from `main` `e3c9e67`). Nothing here touches Roblox by itself: it is the list of what the owner does in Studio, by hand. Written at the end of the work; the SHA-256 and sizes below are the files as they are on the branch (`tools/world_test.py` fails if this table or the hash block stops matching the files).

**What changes in the game:** nothing, until you approve the integration. The four new ModuleScripts only build something when a script requires them: the world needs the TycoonCore edit in `docs/world_pass_integration.patch`; the icons need the shop pull requests of `docs/SHOP_UX_PROPOSAL.md` (section 5). Until then they can sit in Studio safely, and the two command-bar previews below let you look at everything in edit mode.

## (a) Files to copy

| Script | Studio type and place | State | sha256 | Bytes |
|---|---|---|---|---|
| `WorldArt` | ModuleScript, ServerScriptService | new | `0a9690736ed8a7e60cc4824f12d6d78a04e686b633f976e17a22517c2fc8f558` | 15266 |
| `WorldVisuals` | ModuleScript, ServerScriptService | new | `0d2fb53941e4eaf30db7b43e3b66d55f23e5977aad8c91f077e012b12518cd05` | 55999 |
| `IconArt` | ModuleScript, ReplicatedStorage | new | `83a43be6471c597a15a6f2ffcf1f7712fadc3d5e348b3b8a10c067b702236915` | 30741 |
| `IconVisuals` | ModuleScript, ReplicatedStorage | new | `f4543a25877c459389553663fc413eadb3bb14170598e3f2e1f3435ee0f491e4` | 55083 |
| `TycoonCore` | Script, ServerScriptService | **only after approval**: `main`'s file (at e3c9e67) with `docs/world_pass_integration.patch` applied; valid for that file only (`--regen-patch`) | `5a984905708e32e611f3d84c3f22cb91e21eba11421deb12282e3e1316ce38fb` | 35508 |

The files use `\n` line endings and end with one newline. Studio may drop that last newline or add one more: the hash check (d) accepts both, and nothing else. Every other script stays exactly as on `main` (TycoonCore on `main` is `77ce9c43...61aa9`, 34330 bytes, as in docs/STUDIO_SYNC.md).

## (b) Studio-only settings

Nothing new. The Baseplate's grass color, the Lighting values and `StreamingEnabled` stay as docs/STUDIO_SYNC.md (b) and the place have them. The world pass reads two **Studio facts** the owner measured and never changes them: `Workspace.Baseplate` 2048 x 16 x 2048 at (0, -8, 0), and `Workspace.SpawnLocation` 12 x 1 x 12 at (-1, 0.5, -1). The world preview prints `OK studio facts` when the place still matches them; if it prints `PROBLEM`, write the real numbers into `WorldArt.Site` (and tell the next Claude session: the tests use them).

## (c) Steps on the Mac

1. **Put the branch's files in their own folder.** In Terminal, in the project folder (for example `cd ~/Developer/startup-to-ipo-clean`):
   ```
   git fetch
   git worktree add ~/Developer/world-studio origin/world-icons-pass
   ```
   This makes a separate folder, `~/Developer/world-studio`, with the branch's files; your own folder and branch are not touched. Open that folder in VS Code (**File > Open Folder...** and pick `world-studio`, or `code ~/Developer/world-studio`) and copy the files from there. When you are done with it, remove it from the project folder: `git worktree remove ~/Developer/world-studio`. (Once the branch is merged, the files are on `main`: pull `main` instead.)
2. **Create the four ModuleScripts** (right-click the service > Insert Object > ModuleScript, rename it exactly), then open each `.lua` file, select all, copy, and paste over the new script's whole source. Where each one goes:
   - `ServerScriptService > WorldArt` (ModuleScript, from `WorldArt.lua`)
   - `ServerScriptService > WorldVisuals` (ModuleScript, from `WorldVisuals.lua`)
   - `ReplicatedStorage > IconArt` (ModuleScript, from `IconArt.lua`)
   - `ReplicatedStorage > IconVisuals` (ModuleScript, from `IconVisuals.lua`)

   The icon modules sit next to `CreatureConfig`, `CreatureModels` and `ShopConfig`, which the icons read. No other script changes.
3. **Check the hashes:** paste block (d) into **View > Command Bar**, press Enter. Every line must say `OK`.
4. **Look at the world:** paste the world preview block, press Enter. Every line must say `OK` (a `NOTE` line names a hand-placed part the world would overlap). Then look around with the checklist in (f).
5. **Look at the icons:** paste the icon preview block, press Enter. Every line must say `OK`. Then the light test block (one lit cube, on top of the icon sheet) and the checklist in (f). To hide the sheet for a moment without deleting it, untick `Enabled` on `StarterGui.PREVIEW_ICONS`.
6. **Before any playtest:** paste the **cleanup block** (e), press Enter, then the **check block** (e): it must print `OK`.
7. **Only after you approve the integration:** claim `TycoonCore` in CONTRIBUTING.md on a branch. The patch's hash and line numbers are valid for `main` at `e3c9e67` only (its "Made for:" line). If `main`'s `TycoonCore.lua` changed since, first regenerate them on that branch: `python3 tools/world_test.py --regen-patch` (it rewrites the patch and the TycoonCore row in (a), and prints the new hash). Then, at merge time, run `python3 tools/world_test.py --integration --review --strict-patch`: it must pass. `--strict-patch` fails ("patch needs regenerating") if the patch applies only with an offset or fuzz, or if its Made for / Result lines, its line numbers, its hunk headers or the TycoonCore row in (a) are not what `--regen-patch` writes; without the flag the same findings are only a `NOTE`. Then `git apply docs/world_pass_integration.patch`, check that the file's hash is the one in (a), paste it into the Script `TycoonCore`, F5. The world is built when the server starts (the Output shows no `World visuals` warning). Test > Device at 320 x 568 and 667 x 375.
8. **Before publishing:** paste the check block (e) again: it must print `OK` (if it prints `FAIL`, run the cleanup block). Then **View > Drafts:** commit every draft. Publish with **Shut down all servers**, as always (docs/PUBLISH_RULES.md). No save section, no remote, no Max Players change: the rollback floor stays the same.

## (d) Hash check (command bar)

The same SHA-256 code as docs/STUDIO_SYNC.md (checked against `sha256sum`, and run by `tools/world_test.py` on these four files).

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

local WANT = {
	WorldArt = { "0a9690736ed8a7e60cc4824f12d6d78a04e686b633f976e17a22517c2fc8f558", 15266, "ServerScriptService" },
	WorldVisuals = { "0d2fb53941e4eaf30db7b43e3b66d55f23e5977aad8c91f077e012b12518cd05", 55999, "ServerScriptService" },
	IconArt = { "83a43be6471c597a15a6f2ffcf1f7712fadc3d5e348b3b8a10c067b702236915", 30741, "ReplicatedStorage" },
	IconVisuals = { "f4543a25877c459389553663fc413eadb3bb14170598e3f2e1f3435ee0f491e4", 55083, "ReplicatedStorage" },
}
for name, want in pairs(WANT) do
	local script = game:GetService(want[3]):FindFirstChild(name)
	if not script then
		print(name, "MISSING (create it in " .. want[3] .. ")")
	else
		local source = script.Source
		local function matches(text)
			return #text == want[2] and sha256(text) == want[1]
		end
		-- the file as it is, or with its last newline dropped by Studio, or with one newline added by Studio
		local ok = matches(source) or matches(source .. "\n") or (string.sub(source, -2) == "\n\n" and matches(string.sub(source, 1, -2)))
		print(name, ok and "OK" or "DIFFERENT", #source, "bytes")
	end
end
```

## The world preview (command bar)

Only to look at the world in edit mode; it never plays the game. Paste the block into **View > Command Bar** and press Enter. It needs the two ModuleScripts `WorldArt` and `WorldVisuals` in **ServerScriptService** (paste them from the repo first). It builds `Workspace.PREVIEW_WORLD` (the world, plus see-through ghosts where the plots and the VIP Lounge stand once the game runs), then prints one line per check: `OK` or `PROBLEM` and the first problem. It also checks the two Studio facts against the real SpawnLocation and Baseplate (read only), that they were left untouched, and lists any part already in the Workspace that the world would go into (`NOTE`). Running it again replaces the old preview.

**Remove `Workspace.PREVIEW_WORLD` before a playtest and before publishing** with the cleanup block (e) (or select it in the Explorer and press Delete): in a playtest of the wired-in world the two would lie on top of each other.

```lua
-- World preview: builds Workspace.PREVIEW_WORLD and prints one line per check. Delete PREVIEW_WORLD before publishing.
local SSS = game:GetService("ServerScriptService")
local artModule, visualsModule = SSS:FindFirstChild("WorldArt"), SSS:FindFirstChild("WorldVisuals")
assert(artModule and visualsModule, "First create the ModuleScripts WorldArt and WorldVisuals in ServerScriptService")
-- A fresh copy of each module, so a change you just pasted is used (the command bar keeps what it required before)
local WorldArt = require(artModule:Clone())
local WorldVisuals = require(visualsModule:Clone())
local old = workspace:FindFirstChild("PREVIEW_WORLD")
if old then
	old:Destroy()
end
local spawn = workspace:FindFirstChildWhichIsA("SpawnLocation", true)
local baseplate = workspace:FindFirstChild("Baseplate")
local keep = {}
if spawn then
	table.insert(keep, spawn)
end
if baseplate then
	table.insert(keep, baseplate)
end
local before = WorldVisuals.snapshot(keep)
local site = WorldVisuals.site(WorldArt)
local folder = Instance.new("Folder")
folder.Name = "PREVIEW_WORLD"
local world = WorldVisuals.build(folder, WorldArt, site)
WorldVisuals.ghosts(folder, site)
folder.Parent = workspace
local function report(name, problems, word)
	local more = #problems > 1 and string.format(" (and %d more)", #problems - 1) or ""
	print(#problems == 0 and "OK" or (word or "PROBLEM"), name, (problems[1] or "") .. more)
end
for _, result in ipairs(WorldVisuals.checks(world, WorldArt, site)) do
	report(result.name, result.problems)
end
report("studio facts", WorldVisuals.studioFacts(site, spawn, baseplate))
report("untouched", WorldVisuals.compare(before))
local others = {}
for _, d in ipairs(workspace:GetDescendants()) do
	-- Terrain is a BasePart too, but it is not a hand-placed part (its box is the whole map): never a clash
	if d:IsA("BasePart") and d ~= baseplate and not d:IsA("Terrain") and not d:IsDescendantOf(folder) then
		table.insert(others, d)
	end
end
report("clashes with parts already in the Workspace", WorldVisuals.clashes(world, others), "NOTE")
local parts, lights = 0, 0
for _, d in ipairs(world:GetDescendants()) do
	if d:IsA("BasePart") then
		parts += 1
	elseif d:IsA("PointLight") then
		lights += 1
	end
end
print(string.format("PREVIEW_WORLD: %d parts (budget %d), %d lights (budget %d). Delete it before publishing.",
	parts, WorldArt.Budget.parts, lights, WorldArt.Budget.lights))
```

## The icon preview (command bar)

Only to look at the icons in Studio; it never plays the game. It needs `IconArt` and `IconVisuals` as ModuleScripts in **ReplicatedStorage** (next to the existing `CreatureConfig`, `CreatureModels` and `ShopConfig`). Paste the block into **View > Command Bar** and press Enter: it builds a ScreenGui **`StarterGui.PREVIEW_ICONS`** with every icon in a grid at card size (56 px), each with a caption (its group and its drawing's name), the HUD icons on their real button colors, and prints one line per check (`OK` or `PROBLEM` and the first problem). It shows all 18 3D icons at once (it builds them with `IconVisuals.buildUncapped`, outside the cap); in the game every icon goes through the cap of 8 ViewportFrames for the whole client, and a card past it shows its drawn fallback. Running it again replaces the old sheet.

**Remove `StarterGui.PREVIEW_ICONS` before any playtest and before publishing** with the cleanup block (e): everything in StarterGui is copied onto every player's screen. To hide it for a moment while you look at the world, untick its `Enabled` (the block sets it on).

```lua
-- Icon preview: builds StarterGui.PREVIEW_ICONS with every icon and prints one line per check. Delete it before publishing.
local RS = game:GetService("ReplicatedStorage")
local StarterGui = game:GetService("StarterGui")
local artModule, visualsModule = RS:FindFirstChild("IconArt"), RS:FindFirstChild("IconVisuals")
assert(artModule and visualsModule, "First create the ModuleScripts IconArt and IconVisuals in ReplicatedStorage")
-- A fresh copy of the two new modules, so a change you just pasted is used (the command bar keeps what it required before)
local IconArt = require(artModule:Clone())
local IconVisuals = require(visualsModule:Clone())
local CreatureConfig = require(RS:FindFirstChild("CreatureConfig"))
local CreatureModels = require(RS:FindFirstChild("CreatureModels"))
local ShopConfig = require(RS:FindFirstChild("ShopConfig"))
local deps = { CreatureConfig = CreatureConfig, CreatureModels = CreatureModels }
-- What needs an icon: the game's own lists (the Office upgrades are IconArt's, TycoonCore is a server Script)
local expect = { Office = {}, Eggs = {}, Creatures = {}, Shop = {}, Hud = { "Eggs", "Shop", "Team", "Poach", "Ipo" }, rarity = {}, noText = {} }
for key in pairs(IconArt.Office) do
	table.insert(expect.Office, key)
end
table.sort(expect.Office)
for _, egg in ipairs(CreatureConfig.Eggs) do
	table.insert(expect.Eggs, egg.key)
end
for _, creature in ipairs(CreatureConfig.Creatures) do
	table.insert(expect.Creatures, creature.key)
	expect.rarity[creature.key] = creature.rarity
end
for _, list in ipairs({ ShopConfig.Passes, ShopConfig.Products }) do
	for _, item in ipairs(list) do
		table.insert(expect.Shop, item.key)
		if item.changesOdds then
			expect.noText[item.key] = true
		end
	end
end
-- The HUD buttons' own colors (EmployeeClient, ShopClient, PoachClient, IpoClient), to judge the light HUD icons on them
local HUD_COLORS = { Eggs = { 70, 120, 255 }, Shop = { 0, 200, 90 }, Team = { 70, 120, 255 }, Poach = { 225, 95, 60 }, Ipo = { 225, 150, 20 } }
local old = StarterGui:FindFirstChild("PREVIEW_ICONS")
if old then
	old:Destroy()
end
local gui = Instance.new("ScreenGui")
gui.Name = "PREVIEW_ICONS"
gui.ResetOnSpawn = false
gui.DisplayOrder = 50
gui.Enabled = true -- untick Enabled in Properties to hide the sheet without deleting it
local sheet = Instance.new("ScrollingFrame")
sheet.Name = "Sheet"
sheet.Position = UDim2.fromOffset(16, 16)
sheet.Size = UDim2.new(1, -32, 1, -32)
sheet.BackgroundColor3 = Color3.fromRGB(28, 30, 38)
sheet.AutomaticCanvasSize = Enum.AutomaticSize.Y
sheet.CanvasSize = UDim2.new()
sheet.Parent = gui
local layout = Instance.new("UIGridLayout")
layout.CellSize = UDim2.fromOffset(104, 104)
layout.CellPadding = UDim2.fromOffset(8, 8)
layout.SortOrder = Enum.SortOrder.LayoutOrder
layout.Parent = sheet
local icons, order = {}, 0
for _, group in ipairs(IconVisuals.GROUPS) do
	for _, key in ipairs(expect[group]) do
		order += 1
		local cell = Instance.new("Frame")
		cell.Name = group .. "_" .. order
		cell.LayoutOrder = order
		cell.BackgroundColor3 = Color3.fromRGB(42, 45, 56)
		cell.Parent = sheet
		local slot = Instance.new("Frame")
		slot.Name = "Slot"
		slot.AnchorPoint = Vector2.new(0.5, 0)
		slot.Position = UDim2.new(0.5, 0, 0, 8)
		slot.Size = UDim2.fromOffset(56, 56)
		slot.BackgroundTransparency = 1
		local back = HUD_COLORS[key]
		if group == "Hud" and back then
			slot.BackgroundTransparency = 0
			slot.BackgroundColor3 = Color3.fromRGB(back[1], back[2], back[3])
			local round = Instance.new("UICorner")
			round.CornerRadius = UDim.new(0, 14)
			round.Parent = slot
		end
		slot.Parent = cell
		local icon = IconVisuals.buildUncapped(slot, IconArt, group, key, 56, deps)
		local caption = Instance.new("TextLabel")
		caption.Name = "Caption"
		caption.Position = UDim2.new(0, 4, 1, -32)
		caption.Size = UDim2.new(1, -8, 0, 28)
		caption.BackgroundTransparency = 1
		caption.TextScaled = true
		caption.TextColor3 = Color3.fromRGB(235, 238, 245)
		caption.Font = Enum.Font.GothamBold
		caption.Text = group .. ": " .. (icon and icon:GetAttribute("Recipe") or "MISSING")
		caption.Parent = cell
		if icon then
			table.insert(icons, icon)
		end
	end
end
gui.Parent = StarterGui
for _, result in ipairs(IconVisuals.checks(IconArt, icons, expect)) do
	local more = #result.problems > 1 and string.format(" (and %d more)", #result.problems - 1) or ""
	print(#result.problems == 0 and "OK" or "PROBLEM", result.name, (result.problems[1] or "") .. more)
end
local views = 0
for _, icon in ipairs(icons) do
	if icon:FindFirstChild("View") then
		views += 1
	end
end
print(string.format("PREVIEW_ICONS: %d icons (%d 3D, %d drawn). The game keeps at most %d 3D icons alive; this sheet shows all. Delete it before publishing.",
	#icons, views, #icons - views, IconArt.Style.viewportCap))
```

## The light test (command bar)

Roblox's `ViewportFrame.LightDirection` was not checked in Studio: the icons assume it is the way the light travels (IconArt `Style.lightDirection = { 1, -1, -1 }` in the camera's frame: toward the right, down and away, so lit from the picture's top-left). This block shows one white cube lit exactly the way every 3D icon is, at 240 px, as the frame `LightTest` on top of the icon sheet in `StarterGui.PREVIEW_ICONS` (it makes that ScreenGui if the icon preview did not, and turns it on). So it adds no preview object of its own: the cleanup block removes it with the sheet. To see the whole sheet again, delete `PREVIEW_ICONS.LightTest` or run the icon preview again. It needs `IconArt` and `IconVisuals` in ReplicatedStorage.

```lua
-- Light test: adds LightTest, one white cube lit like every 3D icon, to StarterGui.PREVIEW_ICONS (made if missing).
-- The cleanup block removes it with the icon sheet.
local RS = game:GetService("ReplicatedStorage")
local StarterGui = game:GetService("StarterGui")
local artModule, visualsModule = RS:FindFirstChild("IconArt"), RS:FindFirstChild("IconVisuals")
assert(artModule and visualsModule, "First create the ModuleScripts IconArt and IconVisuals in ReplicatedStorage")
local IconArt = require(artModule:Clone())
local IconVisuals = require(visualsModule:Clone())
local gui = StarterGui:FindFirstChild("PREVIEW_ICONS")
if not gui then
	gui = Instance.new("ScreenGui")
	gui.Name = "PREVIEW_ICONS"
	gui.ResetOnSpawn = false
	gui.DisplayOrder = 50
	gui.Parent = StarterGui
end
gui.Enabled = true
local old = gui:FindFirstChild("LightTest")
if old then
	old:Destroy()
end
local art = table.clone(IconArt)
art.Models = { LightCube = { { name = "Cube", shape = "Block", size = { 2, 2, 2 }, offset = { 0, 1, 0 }, color = "white", material = "SmoothPlastic" } } }
local slot = Instance.new("Frame")
slot.Name = "LightTest"
slot.Position = UDim2.fromOffset(24, 24)
slot.Size = UDim2.fromOffset(240, 240)
slot.BackgroundColor3 = Color3.fromRGB(28, 30, 38)
slot.ZIndex = 10 -- above the icon sheet
local view = IconVisuals.buildModel(slot, art, { kind = "model", model = "LightCube", view = { yaw = -28, pitch = 22 } }, 240)
slot.Parent = gui
print(view and "OK light test built" or "PROBLEM light test not built",
	"PREVIEW_ICONS.LightTest: a white cube seen like the Office props. Lit from the top-left: its top face brightest, its right-hand face the darkest.")
```

**What to look at:** the top face is the brightest and the left-hand face is brighter than the right-hand one. If the right-hand face is the brighter one (lit from the bottom-right), `LightDirection` works the other way: write `lightDirection = { -1, 1, 1 }` in IconArt's `Style`, paste IconArt again and rerun this block and the icon preview (and tell the next Claude session: `tools/icon_test.py` pins the current value).

## (e) Remove the previews before a playtest and before publishing

| Object | Made by | Why it must go |
|---|---|---|
| `Workspace.PREVIEW_WORLD` | the world preview block | it lies where the wired-in world would be built (two copies on top of each other flicker), and it is not part of the game |
| `StarterGui.PREVIEW_ICONS` | the icon preview block and the light test block (its `LightTest` frame) | everything in StarterGui is copied onto every player's screen |
| `Workspace.PREVIEW_STAGES` | the plot visuals' preview (docs/STUDIO_SYNC.md) | still on the ROADMAP's before-publish list (item m), if it is there |

**Before a playtest:** the cleanup block, then the check block (it must print `OK`).
**Before publishing:** the check block (it must print `OK`; if it prints `FAIL`, the cleanup block, then the check block again).

No game object is named `PREVIEW_...`: only these Studio previews are. The cleanup block removes exactly these three, by their exact name and place (directly in `Workspace` or `StarterGui`), and nothing else. Any other object whose name starts with `PREVIEW_` (anywhere in `Workspace` or `StarterGui`, or one of the three names somewhere else) is only reported: look at it and delete it by hand if it is an old preview. An older light test left `StarterGui.PREVIEW_LIGHT`: delete that one by hand.

### The cleanup block (command bar)

It destroys `Workspace.PREVIEW_STAGES`, `Workspace.PREVIEW_WORLD` and `StarterGui.PREVIEW_ICONS` (everything inside them goes with them), prints what it removed, prints `unknown PREVIEW_ object: <path>, delete it by hand` for every other `PREVIEW_` object it finds (it never deletes one), and ends with `OK` or `FAIL`.

```lua
-- Cleanup: destroys the three Studio previews (Workspace.PREVIEW_STAGES, Workspace.PREVIEW_WORLD, StarterGui.PREVIEW_ICONS)
-- and nothing else. Every other PREVIEW_ object is only reported, never deleted: delete it by hand.
local StarterGui = game:GetService("StarterGui")
local function known(d)
	return (d.Parent == workspace and (d.Name == "PREVIEW_STAGES" or d.Name == "PREVIEW_WORLD"))
		or (d.Parent == StarterGui and d.Name == "PREVIEW_ICONS")
end
local removed, unknown = {}, {}
for _, place in ipairs({ workspace, StarterGui }) do
	for _, d in ipairs(place:GetChildren()) do
		if known(d) then
			table.insert(removed, d:GetFullName())
			d:Destroy()
		end
	end
end
for _, place in ipairs({ workspace, StarterGui }) do
	for _, d in ipairs(place:GetDescendants()) do
		if string.sub(d.Name, 1, 8) == "PREVIEW_" then
			table.insert(unknown, d:GetFullName())
			print("unknown PREVIEW_ object: " .. d:GetFullName() .. ", delete it by hand")
		end
	end
end
print("Removed: " .. (#removed > 0 and table.concat(removed, ", ") or "nothing (no preview was there)"))
print(#unknown == 0 and "OK no PREVIEW_ object is left in Workspace or StarterGui"
	or ("FAIL " .. #unknown .. " unknown PREVIEW_ object(s) left, not deleted: " .. table.concat(unknown, ", ")))
```

### The check block (command bar)

It changes nothing: `OK`, or `FAIL` and every `PREVIEW_` object in `Workspace` or `StarterGui`, each marked `known` (one of the three, or inside one: the cleanup block removes it) or `unknown` (delete it by hand).

```lua
-- Check: OK, or FAIL and every PREVIEW_ object in Workspace or StarterGui, known or unknown. Changes nothing.
local StarterGui = game:GetService("StarterGui")
local function known(d) -- one of the three previews, or inside one (the cleanup block removes it with it)
	while d ~= nil and d ~= workspace and d ~= StarterGui do
		if (d.Parent == workspace and (d.Name == "PREVIEW_STAGES" or d.Name == "PREVIEW_WORLD"))
			or (d.Parent == StarterGui and d.Name == "PREVIEW_ICONS") then
			return true
		end
		d = d.Parent
	end
	return false
end
local found = {}
for _, place in ipairs({ workspace, StarterGui }) do
	for _, d in ipairs(place:GetDescendants()) do
		if string.sub(d.Name, 1, 8) == "PREVIEW_" then
			table.insert(found, d:GetFullName() .. (known(d) and " (known: the cleanup block removes it)" or " (unknown: delete it by hand)"))
		end
	end
end
print(#found == 0 and "OK no PREVIEW_ object in Workspace or StarterGui" or ("FAIL " .. #found .. " PREVIEW_ object(s) still there: " .. table.concat(found, ", ")))
```

## (f) What to look at in Studio (only your eyes can judge these)

**The world** (after the world preview, in edit mode; then in a playtest once it is wired in)
- [ ] The paths, kerbs and lawns next to the Baseplate's grass under the place's real Lighting (ClockTime 14, haze, color correction): too pale, too gray, too busy?
- [ ] Stand where a player lands on a plot (its middle, a little to the front) and look out of the front, like the default camera: the front street, your plot's number sign across it (is the number readable?), lamps and trees not in the way.
- [ ] The arch's BUILD YOUR STARTUP from the spawn plaza: readable, the right size?
- [ ] The far hills through the haze: a nice horizon, or too bright, too dark, too round?
- [ ] Walk it: spawn, plaza, under the arch, around the lounge, the forecourt at the door, the back street, between two plots, the front street, a plot's walk. Does it read as a little startup street?
- [ ] The forecourt: the door and the spot where a non-VIP is put back (0, 88) are clear; the two lit lamps don't block the door.
- [ ] Low camera angles at path joints and the plaza: any flicker (z-fighting)? The tests check every face plane, but your eyes have the final say.
- [ ] In a playtest on a phone (Test > Device) once wired in: frame rate around the plots, and whether far parts pop in and out (StreamingEnabled) in a way that bothers you.

**The icons** (after the icon preview)
- [ ] Every icon reads at 56 px: zoom the Studio view to 100%, then Test > Device on a small phone.
- [ ] The light test (its block, above (e)): the white cube is lit from the top-left (top face brightest, right-hand face darkest). This is the only check of `LightDirection`'s meaning; if it is the other way round, see the note under the block.
- [ ] The 3D icons: nothing cut off, nothing too small, lit from the top-left, not too dark (the ViewportFrame has its own ambient light).
- [ ] The outline weight and the round plates: chunky cartoon, or too heavy?
- [ ] The HUD icons on their real button colors: enough contrast (especially the magnet on POACH and the chart on IPO)?
- [ ] The clover shows no text at all; the coin says 2x, the chair +3, the bill and the bag $.
- [ ] Tap behavior is not in the previews (it needs the shop pull request).

## (g) The pictures on GitHub

`docs/previews/world_topdown.svg` (the world from above, with a scale bar and the whole Baseplate) and `docs/previews/icons_sheet.svg` (every icon at 96 px) are drawn by `tools/render_previews.py` from the same data, through the tests' fake Roblox. They are **approximations** (boxes from above, flat shading, no materials or real fonts), to look at before opening Studio. After a change to `WorldArt` or `IconArt`, run `python3 tools/render_previews.py` again; `--check` says whether they are up to date, and fails if a text of the top-down picture runs past its edge, lies on another text, or a sign's label lies on a tree, lamp or bush (estimated text sizes).
