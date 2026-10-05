# Studio sync: the world and icons pass

Branch `world-icons-pass`. Nothing here touches Roblox by itself: it is what the owner does in Studio. (This file is completed at the end of the work: files to copy with their SHA-256, the manual steps, what to delete before publishing and what to look at.)

## The world preview (command bar)

Only to look at the world in edit mode; it never plays the game. Paste the block into **View > Command Bar** and press Enter. It needs the two ModuleScripts `WorldArt` and `WorldVisuals` in **ServerScriptService** (paste them from the repo first). It builds `Workspace.PREVIEW_WORLD` (the world, plus see-through ghosts where the plots and the VIP Lounge stand once the game runs), then prints one line per check: `OK` or `PROBLEM` and the first problem. It also checks the two Studio facts against the real SpawnLocation and Baseplate (read only), that they were left untouched, and lists any part already in the Workspace that the world would go into (`NOTE`). Running it again replaces the old preview.

**Delete `Workspace.PREVIEW_WORLD` before publishing** (select it in the Explorer, press Delete), and before a playtest of the wired-in world (the two would lie on top of each other).

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
	if d:IsA("BasePart") and d ~= baseplate and not d:IsDescendantOf(folder) then
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

Only to look at the icons in Studio; it never plays the game. It needs `IconArt` and `IconVisuals` as ModuleScripts in **ReplicatedStorage** (next to the existing `CreatureConfig`, `CreatureModels` and `ShopConfig`). Paste the block into **View > Command Bar** and press Enter: it builds a ScreenGui **`StarterGui.PREVIEW_ICONS`** with every icon in a grid at card size (56 px), each with a caption (its group and its drawing's name), the HUD icons on their real button colors, and prints one line per check (`OK` or `PROBLEM` and the first problem). It shows all 18 3D icons at once; the game never has more than 8 alive (the cap). Running it again replaces the old sheet.

**Delete `StarterGui.PREVIEW_ICONS` before publishing**, and before any playtest (everything in StarterGui is copied onto every player's screen).

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
		local icon = IconVisuals.build(slot, IconArt, group, key, 56, deps)
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
