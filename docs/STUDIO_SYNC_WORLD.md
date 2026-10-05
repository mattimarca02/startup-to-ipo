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
