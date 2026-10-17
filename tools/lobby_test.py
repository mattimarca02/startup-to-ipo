#!/usr/bin/env python3
"""Tests for the lobby and garages plan (docs/LOBBY_GARAGE_PROPOSAL.md), outside Studio.

Run:   python3 tools/lobby_test.py

It needs git, the commit 99eed7b (every full clone of the repo has it; a shallow clone may not) and the free Luau
command-line tool (https://github.com/luau-lang/luau/releases, the "luau" file from luau-macos.zip, luau-windows.zip
or luau-ubuntu.zip). Put it on your PATH, or point to it:
       LUAU=/path/to/luau python3 tools/lobby_test.py

PR L0 (this file's first version) only adds the CLAIMLOAD markers to TycoonCore.lua, around the join load that PR L3
moves into claimGarage: onPlayerAdded from `local saved, ok = load(player)` to `data.ready = true`, lines 774-863 of
TycoonCore.lua at main 99eed7b (the proposal's section 2.1). PR L1 (the plot frame) changes ten places outside the
markers and none inside: every garage position goes through plotFrame, all turns 0. It checks that:
- there is one CLAIMLOAD-START line and one CLAIMLOAD-END line, comment lines only, inside onPlayerAdded;
- the text between them is lines 774-863 of TycoonCore.lua at 99eed7b (read with git show), byte for byte (L1 keeps
  the room line's plotCenter(slot): PlotVisuals takes the turn from the Floor);
- TycoonCore.lua without its CLAIMLOAD comment lines is the file at 99eed7b with L1's ten plot-frame edits (L1_EDITS,
  each old text found once and replaced once), byte for byte: any other change outside the markers fails;
- docs/STUDIO_SYNC_LOBBY.md's L1 section gives the real SHA-256 and size of the five scripts L1 changes, and its hash
  block (run in Luau against a fake Studio) says ALL OK for the real files and NOT YET for a changed one;
- its "Lobby all" section does the same for every script lobby-all created or changed. Both sections are history:
  they are checked against the files as merged (L1_COMMIT, ALL_COMMIT, read with git show), never the folder, so a
  later edit of one of those scripts never fails this test. New Studio steps go to docs/STUDIO_SYNC_BATCH.md.
Then it breaks TycoonCore.lua on purpose, in memory (mutation runs): each must be caught by its named check, never
by a crash. Running the marked block with fakes (a DataStore, the modules, a player leaving at each yield) is PR L3's.
The plot frame's own tests (turns 0, 90, 180, 270; every "center + offset"; the mutants) are in tools/daily_test.py.

It changes nothing in the game or in Studio. It never edits the other test files.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "99eed7b"            # main before L0: the CLAIMLOAD block is compared with this commit's TycoonCore.lua
FIRST, LAST = 774, 863      # the block's lines at BASE (docs/LOBBY_GARAGE_PROPOSAL.md section 2.1)
START = "-- CLAIMLOAD-START"
END = "-- CLAIMLOAD-END"
SYNC_DOC = "docs/STUDIO_SYNC_LOBBY.md"
L1_HEADING = "## L1. Plot frame (nothing visible)"
L1_COMMIT = "f6a546f"       # main with L1 merged: the L1 section's table is history, checked against the files of this commit
ALL_HEADING = "## Lobby all (L2 to L5)"
ALL_COMMIT = "2df1410"      # main with lobby-all merged (PR #32): the Lobby all section is history, checked against the files of this commit
# Every script lobby-all creates or changes: (file, Studio class, Studio place, "new" or "changed"). The "Lobby all"
# section's table and hash block must give each one's SHA-256 and size as lobby-all merged it (ALL_COMMIT), so a later
# edit of one of these files never fails this test: new Studio steps go to docs/STUDIO_SYNC_BATCH.md.
ALL_SCRIPTS = (("TycoonCore", "Script", "ServerScriptService", "changed"), ("ShopClient", "LocalScript", "StarterPlayerScripts", "changed"),
               ("PlotBuilding", "ModuleScript", "ServerScriptService", "new"),
               ("PlotBuildingVisuals", "ModuleScript", "ServerScriptService", "new"), ("BuildingClient", "LocalScript", "StarterPlayerScripts", "new"),
               ("LobbyConfig", "ModuleScript", "ReplicatedStorage", "new"), ("LobbyClient", "LocalScript", "StarterPlayerScripts", "new"),
               ("ShopServer", "ModuleScript", "ServerScriptService", "changed"), ("IpoClient", "LocalScript", "StarterPlayerScripts", "changed"),
               ("WorldArt", "ModuleScript", "ServerScriptService", "changed"), ("WorldVisuals", "ModuleScript", "ServerScriptService", "changed"),
               # unchanged since main (lobby L1): the hash block checks them too, so one run covers every lobby script
               ("EmployeeServer", "ModuleScript", "ServerScriptService", "as on main"), ("IpoServer", "ModuleScript", "ServerScriptService", "as on main"),
               ("PlotVisuals", "ModuleScript", "ServerScriptService", "as on main"), ("EmployeeClient", "LocalScript", "StarterPlayerScripts", "as on main"))
# The five scripts PR L1 changes: (file, Studio class, Studio place)
L1_SCRIPTS = (("TycoonCore", "Script", "ServerScriptService"), ("EmployeeServer", "ModuleScript", "ServerScriptService"),
              ("IpoServer", "ModuleScript", "ServerScriptService"), ("PlotVisuals", "ModuleScript", "ServerScriptService"),
              ("EmployeeClient", "LocalScript", "StarterPlayerScripts"))

# PR L1's edits outside the CLAIMLOAD markers: (text at BASE, its L1 text). Applied in order, each old text must be in
# the file exactly once. Nothing else outside the markers may change (the "outside" check).
L1_EDITS = (
    # the turn of each garage, next to MAX_PLOTS
    ("local MAX_PLOTS = 6\n",
     "local MAX_PLOTS = 6\n-- Each garage's turn in degrees, one per slot (quarter turns only: 0, 90, 180 or 270). Offsets inside a garage are in\n"
     "-- its own frame (+X right, +Z the front, toward the signs), so they turn with it (plotFrame). All 0 for now: every\n"
     "-- garage stands as it always has (docs/LOBBY_GARAGE_PROPOSAL.md, PR L1; the ring of PR L4 turns them).\n"
     "local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }\n"),
    # makePart places a part by CFrame when it is given one (a part in a garage's frame)
    ("\tp.Position = position\n",
     "\tif typeof(position) == \"CFrame\" then\n\t\tp.CFrame = position -- a part placed in a garage's frame, turned with it\n"
     "\telse\n\t\tp.Position = position\n\tend\n"),
    # plotFrame, right after plotCenter (which stays as it is)
    ("\treturn Vector3.new(startX + (slot - 1) * PLOT_SPACING, 0.5, 150)\nend\n",
     "\treturn Vector3.new(startX + (slot - 1) * PLOT_SPACING, 0.5, 150)\nend\n\n"
     "-- A garage's frame: its center, turned by its GARAGE_TURNS. frame * offset is where an offset in the garage lands in\n"
     "-- the world, at any turn (plotFrame(slot).Position is plotCenter(slot)). Quarter turns are exact (cos and sin are -1, 0\n"
     "-- or 1), so a turned room's boxes stay on the grid: the turn is about +Y, and 90 turns the front (+Z) to world +X.\n"
     "local QUARTER_TURNS = { [0] = { 1, 0 }, [90] = { 0, 1 }, [180] = { -1, 0 }, [270] = { 0, -1 } } -- degrees -> cos, sin\n"
     "local function plotFrame(slot)\n\tlocal center = plotCenter(slot)\n"
     "\tlocal c, s = QUARTER_TURNS[GARAGE_TURNS[slot]][1], QUARTER_TURNS[GARAGE_TURNS[slot]][2]\n"
     "\treturn CFrame.new(center.X, center.Y, center.Z, c, 0, s, 0, 1, 0, -s, 0, c)\nend\n"),
    # spawnItem's plain block
    ("\tlocal pos = plotCenter(data.slot) + itemOffset(i) + Vector3.new(0, 0.5 + upg.size.Y / 2, 0)\n",
     "\tlocal pos = plotFrame(data.slot) * CFrame.new(itemOffset(i) + Vector3.new(0, 0.5 + upg.size.Y / 2, 0))\n"),
    # refreshSign: the next-upgrade sign's spot, post and board
    ("\tlocal pos = plotCenter(data.slot) + SIGN_OFFSET\n"
     "\tlocal post = makePart(data.folder, \"BuySign\", Vector3.new(0.4, 3, 0.4), pos + Vector3.new(0, 1.5, 0), Color3.fromRGB(70, 74, 86), Enum.Material.Metal)\n",
     "\tlocal pos = plotFrame(data.slot) * CFrame.new(SIGN_OFFSET) -- turned with the garage\n"
     "\tlocal post = makePart(data.folder, \"BuySign\", Vector3.new(0.4, 3, 0.4), pos * CFrame.new(0, 1.5, 0), Color3.fromRGB(70, 74, 86), Enum.Material.Metal)\n"),
    ("\tlocal board = makePart(post, \"Board\", Vector3.new(8, 2.6, 0.3), pos + Vector3.new(0, 4.3, 0), Color3.fromRGB(0, 140, 70), Enum.Material.SmoothPlastic)\n",
     "\tlocal board = makePart(post, \"Board\", Vector3.new(8, 2.6, 0.3), pos * CFrame.new(0, 4.3, 0), Color3.fromRGB(0, 140, 70), Enum.Material.SmoothPlastic)\n"),
    # IpoServer and EmployeeServer get the frame (PoachServer keeps plotCenter: it never computes a position)
    ("\tupdateIncome = updateIncome,\n\tplotCenter = plotCenter,\n\tcommitIpo = commitIpo,\n",
     "\tupdateIncome = updateIncome,\n\tplotFrame = plotFrame,\n\tcommitIpo = commitIpo,\n"),
    ("\tupdateIncome = updateIncome,\n\tplotCenter = plotCenter,\n})\n\n-- Poaching",
     "\tupdateIncome = updateIncome,\n\tplotFrame = plotFrame,\n})\n\n-- Poaching"),
    # teleportToPlot: the landing and the look, in the garage's frame
    ("\t-- Land in the middle of the garage, facing the front sign\n\tlocal spawnPos = plotCenter(slot) + Vector3.new(0, 4, 12)\n"
     "\tlocal signPos = plotCenter(slot) + Vector3.new(0, 4, 24)\n",
     "\t-- Land in the middle of the garage, facing the front sign (both in the garage's frame)\n"
     "\tlocal spawnPos = plotFrame(slot) * Vector3.new(0, 4, 12)\n\tlocal signPos = plotFrame(slot) * Vector3.new(0, 4, 24)\n"),
    # the Floor, made in the garage's frame (newPlot takes the room's turn from it)
    ("\tlocal floor = makePart(folder, \"Floor\", Vector3.new(60, 1, 60), plotCenter(slot), Color3.fromRGB(90, 90, 100))\n",
     "\tlocal floor = makePart(folder, \"Floor\", Vector3.new(60, 1, 60), plotFrame(slot), Color3.fromRGB(90, 90, 100)) -- the room takes its turn from it\n"),
)


# PR L2's edits outside the CLAIMLOAD markers (the permanent, closed building), applied after L1_EDITS, each old text found
# exactly once. Nothing between the markers changes: the room line still gets `floor` and `folder`.
L2_EDITS = (
    # the building modules (required in pcall like the plot visuals: a broken building never stops the game), then the
    # garages: built once, the building synced with the stage, the sign, the reset; syncRoom also syncs the building
    ("-- Runs every second (income loop): a new funding stage, or back to the Garage after an IPO,\n"
     "-- swaps the room with a quick flash. The bought props move along.\n"
     "local function syncRoom(data)\n"
     "\tif data.looks and data.looks.stage ~= stageOf(data) then\n"
     "\t\tlooks(\"stage\", PlotVisuals.setStage, data.looks, stageOf(data), true)\n"
     "\tend\n"
     "end\n",
     "-- The closed building around each garage: PlotBuildingVisuals builds it from PlotBuilding (both in ServerScriptService)\n"
     "-- with the 3D kit in ReplicatedStorage.KitModels (Parts where a model is missing), and the client script BuildingClient\n"
     "-- fades it while you are inside. Only looks plus invisible solid outer walls; never saved. Loaded inside pcall: if\n"
     "-- either is missing or broken, the garages stand open, as before.\n"
     "local buildingOk, PlotBuildingVisuals = pcall(require, script.Parent:WaitForChild(\"PlotBuildingVisuals\", 5))\n"
     "local buildingDataOk, PlotBuilding = pcall(require, script.Parent:WaitForChild(\"PlotBuilding\", 5))\n"
     "if not (buildingOk and buildingDataOk) then\n"
     "\twarn(\"Plot buildings are off: \" .. tostring(buildingOk and PlotBuilding or PlotBuildingVisuals))\n"
     "\tPlotBuildingVisuals, PlotBuilding = nil, nil\n"
     "end\n\n"
     "-- The six garages (lobby L2: permanent). Each is Workspace.Garages.Garage<slot>: its Floor (60 x 60, the room's only\n"
     "-- solid part, in the garage's frame), its closed building (PlotBuilding) and its sign. An owner's folder (room, props,\n"
     "-- employees, incubators, signs) stands in it while they play; when they leave, the garage goes back to a new Garage.\n"
     "local garages = {} -- slot -> the garage Model\n\n"
     "-- The building of a garage at a funding stage (nothing to do when it already shows it). A new building is never\n"
     "-- allowed to trap anyone: a character standing where a solid box now is goes to the garage's landing spot.\n"
     "local buildingWarned = false -- it runs every second: a broken building is told once per server, not every second\n"
     "local function syncBuilding(slot, stage)\n"
     "\tif not (PlotBuildingVisuals and garages[slot]) then return end\n"
     "\tlocal kit = ReplicatedStorage:FindFirstChild(PlotBuilding.KIT_FOLDER)\n"
     "\tlocal ok, model, changed = pcall(PlotBuildingVisuals.sync, garages[slot], plotFrame(slot), PlotBuilding, stage, kit)\n"
     "\tif not ok then\n"
     "\t\tif not buildingWarned then\n"
     "\t\t\tbuildingWarned = true\n"
     "\t\t\twarn(\"Plot buildings: the building failed: \" .. tostring(model))\n"
     "\t\tend\n"
     "\telseif changed then\n"
     "\t\tlocal roots = {}\n"
     "\t\tfor _, other in ipairs(Players:GetPlayers()) do\n"
     "\t\t\tlocal root = other.Character and other.Character:FindFirstChild(\"HumanoidRootPart\")\n"
     "\t\t\tif root then table.insert(roots, root) end\n"
     "\t\tend\n"
     "\t\tpcall(PlotBuildingVisuals.unstick, model, roots, plotFrame(slot) * CFrame.new(0, 4, 12)) -- teleportToPlot's landing\n"
     "\tend\n"
     "end\n\n"
     "-- The name over a garage (\"\" hides it): set when someone moves in, cleared when they leave\n"
     "local function setGarageSign(slot, text)\n"
     "\tlocal sign = garages[slot] and garages[slot]:FindFirstChild(\"GarageSign\")\n"
     "\tlocal gui = sign and sign:FindFirstChildOfClass(\"BillboardGui\")\n"
     "\tif gui then\n"
     "\t\tgui.TextLabel.Text = text\n"
     "\t\tgui.Enabled = text ~= \"\"\n"
     "\tend\n"
     "end\n\n"
     "-- After the owner's leave save: the garage is a new Garage again (Floor and building at stage 1, no name)\n"
     "local function resetGarage(slot)\n"
     "\tlocal garage = garages[slot]\n"
     "\tif not garage then return end\n"
     "\tif PlotVisuals then\n"
     "\t\tlooks(\"floor\", PlotVisuals.styleFloor, garage.Floor, PlotArt, 1)\n"
     "\tend\n"
     "\tsyncBuilding(slot, 1)\n"
     "\tsetGarageSign(slot, \"\")\n"
     "end\n\n"
     "-- Builds the six garages once, when the server starts, before anyone is set up\n"
     "local function buildGarages()\n"
     "\tlocal root = Instance.new(\"Folder\")\n"
     "\troot.Name = \"Garages\"\n"
     "\tfor slot = 1, MAX_PLOTS do\n"
     "\t\tlocal garage = Instance.new(\"Model\")\n"
     "\t\tgarage.Name = \"Garage\" .. slot\n"
     "\t\tgarage:SetAttribute(\"Slot\", slot)\n"
     "\t\tmakePart(garage, \"Floor\", Vector3.new(60, 1, 60), plotFrame(slot), Color3.fromRGB(90, 90, 100)) -- the room takes its turn from it\n"
     "\t\tlocal sign = makePart(garage, \"GarageSign\", Vector3.new(1, 1, 1), plotFrame(slot), Color3.fromRGB(90, 90, 100))\n"
     "\t\tsign.Transparency, sign.CanCollide, sign.CanTouch, sign.CanQuery = 1, false, false, false\n"
     "\t\taddLabel(sign, \"\", 12).Parent.Enabled = false -- the owner's name, over the garage\n"
     "\t\tgarage.Parent = root\n"
     "\t\tgarages[slot] = garage\n"
     "\tend\n"
     "\troot.Parent = workspace\n"
     "\tfor slot = 1, MAX_PLOTS do\n"
     "\t\tresetGarage(slot)\n"
     "\tend\n"
     "end\n"
     "buildGarages()\n\n"
     "-- Runs every second (income loop): a new funding stage, or back to the Garage after an IPO,\n"
     "-- swaps the room with a quick flash (the bought props move along) and the building around it.\n"
     "-- data.debugStage is the Studio Debug button's (in memory only, never saved): it only changes what is shown.\n"
     "local function syncRoom(data)\n"
     "\tlocal stage = data.debugStage or stageOf(data)\n"
     "\tif data.looks and data.looks.stage ~= stage then\n"
     "\t\tlooks(\"stage\", PlotVisuals.setStage, data.looks, stage, true)\n"
     "\tend\n"
     "\tsyncBuilding(data.slot, stage)\n"
     "end\n"),
    # Studio only: a Debug button that steps the room and the building through the five stages (walk every doorway)
    ("\tbuyUpgrade = buyUpgrade, -- the Office tab\n\tupgradeList = upgradeList,\n})\n",
     "\tbuyUpgrade = buyUpgrade, -- the Office tab\n\tupgradeList = upgradeList,\n})\n\n"
     "-- Studio only (the Debug tab exists only in Studio): shows the next funding stage's room and building, to walk every\n"
     "-- doorway. In memory only: the valuation, the save and the stage rule are untouched; a rejoin shows the real stage.\n"
     "if RunService:IsStudio() then\n"
     "\tShopServer.addDebugAction(\"BuildingNextStage\", function(_, data)\n"
     "\t\tdata.debugStage = (data.debugStage or stageOf(data)) % #IpoConfig.Stages + 1\n"
     "\t\treturn \"Showing stage \" .. data.debugStage .. \" (\" .. IpoConfig.Stages[data.debugStage].name .. \"): Studio only, not saved\"\n"
     "\tend)\n"
     "end\n"),
    # the owner's folder stands in their garage
    ("\tfolder.Parent = workspace\n",
     "\tfolder.Parent = garages[slot] -- the owner's room, props, employees and signs stand in their garage\n"),
    # the Floor is the garage's (permanent); the owner's name goes on the garage sign, not on a new billboard per join
    ("\tlocal floor = makePart(folder, \"Floor\", Vector3.new(60, 1, 60), plotFrame(slot), Color3.fromRGB(90, 90, 100)) -- the room takes its turn from it\n"
     "\taddLabel(floor, player.DisplayName .. \"'s Startup\", 12)\n",
     "\tlocal floor = garages[slot].Floor -- permanent (buildGarages): the room takes its turn from it\n"
     "\tsetGarageSign(slot, player.DisplayName .. \"'s Startup\")\n"),
    # the reset on leave, after the leave save and the folder
    ("\t\tdata.folder:Destroy()\n\t\tplotOwners[data.slot] = nil\n",
     "\t\tdata.folder:Destroy()\n\t\tresetGarage(data.slot) -- the garage stays: back to a new Garage, with no name on it\n\t\tplotOwners[data.slot] = nil\n"),
)

# PR L3's edits outside the CLAIMLOAD markers (the claim behind LobbyConfig.ClaimEnabled), applied after L2_EDITS, each
# old text found exactly once. The block itself does not move in the file: onPlayerAdded's head becomes claimGarage's
# head (edit 6) and its tail claimGarage's tail plus the new join (edit 7), so the block's lines are claimGarage's.
# Written with real tabs (the file's), in triple quotes.
L3_EDITS = (
    # the LobbyConfig require, next to IpoConfig
    ('''local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
''',
     '''local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig"))
local LobbyConfig = require(ReplicatedStorage:WaitForChild("LobbyConfig")) -- the garages, the plaza and the claim (ClaimEnabled)
'''),
    # the claim's tables, the garage states and the Free room (in the garages block)
    ('''local garages = {} -- slot -> the garage Model

''',
     '''local garages = {} -- slot -> the garage Model

-- The claim (lobby L3). A joining player stands on the plaza (inPlaza) until they claim a garage. plotOwners[slot] stays
-- the only truth of who has a garage; garageState is only what the garage shows (Free, MovingIn, Taken, Closing).
local inPlaza = {} -- player -> true: joined, no garage yet (written before the join's first yield)
local claims = {} -- UserId -> { slot, leaving }: one garage per account, held until that account's leave save has returned
local claimedAt = {} -- player -> os.clock() of their claim (a Robux receipt waits for the save from then)
local lastClaimAsk = {} -- UserId -> os.clock() of their last claim request (one a second)
local garageState = {} -- slot -> "Free", "MovingIn", "Taken" or "Closing"
local requestClaim -- a prompt's handler (the claim, below onPlayerAdded's helpers)

-- A part of a garage's claim spot (its "ClaimPost" or its "FreeLamp"), or nil
local function claimPart(slot, name)
	local spot = garages[slot] and garages[slot]:FindFirstChild("ClaimSpot")
	return spot and spot:FindFirstChild(name)
end

-- What a garage shows: its State and OwnerName attributes (for display: nothing reads them back), and the claim post's
-- prompt, FREE sign and lamp, which only a Free garage has, and only while the claim is on
local function setGarageState(slot, state, ownerName)
	garageState[slot] = state
	local garage = garages[slot]
	if not garage then return end
	garage:SetAttribute("State", state)
	garage:SetAttribute("OwnerName", ownerName or "")
	local free = state == "Free" and LobbyConfig.ClaimEnabled
	local post = claimPart(slot, "ClaimPost")
	if post then
		post.Transparency = LobbyConfig.ClaimEnabled and 0 or 1
		local prompt = post:FindFirstChildOfClass("ProximityPrompt")
		if prompt then prompt.Enabled = free end
		local gui = post:FindFirstChildOfClass("BillboardGui")
		if gui then
			gui.Enabled = LobbyConfig.ClaimEnabled and state ~= "Taken"
			gui.TextLabel.Text = (state == "Free" and LobbyConfig.Texts.Free) or (state == "MovingIn" and LobbyConfig.Texts.MovingIn) or LobbyConfig.Texts.Closing
		end
	end
	local lamp = claimPart(slot, "FreeLamp")
	if lamp then lamp.Transparency = free and 0 or 1 end
end

-- A Free garage shows today's new-player room: the stage 1 room, with no props (nobody owns any). Looks only.
local function buildFreeRoom(slot)
	local garage = garages[slot]
	if not (garage and PlotVisuals) or garage:FindFirstChild("FreeRoom") then return end
	local folder = Instance.new("Folder")
	folder.Name = "FreeRoom"
	folder.Parent = garage
	looks("free room", PlotVisuals.newPlot, folder, plotFrame(slot).Position, PlotArt, garage.Floor, 1)
end
local function clearFreeRoom(slot)
	local room = garages[slot] and garages[slot]:FindFirstChild("FreeRoom")
	if room then room:Destroy() end
end

'''),
    # the reset builds the Free room and shows the garage Free
    ('''	syncBuilding(slot, 1)
	setGarageSign(slot, "")
end
''',
     '''	syncBuilding(slot, 1)
	setGarageSign(slot, "")
	buildFreeRoom(slot)
	setGarageState(slot, "Free")
end
'''),
    # the claim post, its prompt, the FREE sign and lamp; the Max Players warning
    ('''		addLabel(sign, "", 12).Parent.Enabled = false -- the owner's name, over the garage
		garage.Parent = root
		garages[slot] = garage
	end
	root.Parent = workspace
''',
     '''		addLabel(sign, "", 12).Parent.Enabled = false -- the owner's name, over the garage
		-- The claim post beside the door (lobby L3): the "Claim garage" prompt, the FREE sign and a lamp (Neon, no light).
		-- Never solid, never touched; only shown while the claim is on. Both stand in the garage's ClaimSpot, a Persistent
		-- model: with streaming on, every client has every post (and its prompt) from the start, however far away.
		local spot = Instance.new("Model")
		spot.Name = "ClaimSpot"
		pcall(function()
			spot.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
		end)
		spot.Parent = garage
		local postAt = plotFrame(slot) * CFrame.new(LobbyConfig.Post.x, 1.5, LobbyConfig.Post.z)
		local post = makePart(spot, "ClaimPost", Vector3.new(0.6, 4, 0.6), postAt, Color3.fromRGB(70, 74, 86), Enum.Material.Metal)
		post.CanCollide, post.CanTouch, post.CanQuery = false, false, false
		local lamp = makePart(spot, "FreeLamp", Vector3.new(1, 1, 1), postAt * CFrame.new(0, 2.5, 0), Color3.fromRGB(90, 230, 120), Enum.Material.Neon)
		lamp.CanCollide, lamp.CanTouch, lamp.CanQuery = false, false, false
		local prompt = Instance.new("ProximityPrompt")
		prompt.ActionText = LobbyConfig.Texts.Prompt
		prompt.ObjectText = "Garage " .. slot
		prompt.HoldDuration = LobbyConfig.HoldSeconds
		prompt.MaxActivationDistance = LobbyConfig.PromptDistance
		prompt.RequiresLineOfSight = false
		prompt.Enabled = false
		prompt.Parent = post
		prompt.Triggered:Connect(function(player)
			requestClaim(player, slot)
		end)
		local freeSign = addLabel(post, LobbyConfig.Texts.Free, 4)
		freeSign.TextColor3 = Color3.fromRGB(90, 230, 120)
		freeSign.Parent.Enabled = false
		garage.Parent = root
		garages[slot] = garage
	end
	root.Parent = workspace
	if Players.MaxPlayers > MAX_PLOTS then -- nothing reads Max Players: a 7th player is only kicked (docs/PUBLISH_RULES.md)
		warn(string.format("Max Players is %d but there are %d garages: set it to %d in Creator Hub", Players.MaxPlayers, MAX_PLOTS, MAX_PLOTS))
	end
'''),
    # ShopServer's core gets claimedAt (a receipt waits for the save from the claim)
    ('''	buyUpgrade = buyUpgrade, -- the Office tab
	upgradeList = upgradeList,
})
''',
     '''	buyUpgrade = buyUpgrade, -- the Office tab
	upgradeList = upgradeList,
	claimedAt = function(player) -- when they claimed their garage (nil: not yet): a Robux receipt waits for the save from then
		return claimedAt[player]
	end,
})
'''),
    # onPlayerAdded's slot picking becomes claimGarage's head (the claim written before any yield)
    ('''local function onPlayerAdded(player)
	local slot
	for s = 1, MAX_PLOTS do
		if not plotOwners[s] then
			slot = s
			break
		end
	end
	if not slot then
		player:Kick("This server is full, please join another one.")
		return
	end
	plotOwners[slot] = player

''',
     '''-- Moves a player into a garage: the claim (a prompt, or the server itself while ClaimEnabled is off). The caller asked
-- LobbyConfig.canClaim with no yield since: this writes the claim before anything here can yield, then loads the save
-- exactly as the join always did (the marked block below). The garage is never saved: only the company is.
local function claimGarage(player, slot)
	claims[player.UserId] = { slot = slot }
	plotOwners[slot] = player
	inPlaza[player] = nil
	claimedAt[player] = os.clock()
	player:SetAttribute("Garage", slot)
	setGarageState(slot, "MovingIn", player.DisplayName)
	clearFreeRoom(slot)

'''),
    # claimGarage's tail (Taken), the prompt's request, the auto-claim, the plaza, the new join and the leave handler
    ('''	data.ready = true -- the shop waits for this before granting purchases

	player.CharacterAdded:Connect(function(character)
		teleportToPlot(character, slot)
	end)
	if player.Character then
		task.spawn(teleportToPlot, player.Character, slot)
	end
end
Players.PlayerAdded:Connect(onPlayerAdded)
-- Players already in the server (they joined while this script was still starting) are set up too
for _, existing in ipairs(Players:GetPlayers()) do
	if not playerData[existing] then
		task.spawn(onPlayerAdded, existing)
	end
end

Players.PlayerRemoving:Connect(function(player)
	saveOnLeave(player)
	local data = playerData[player]
	if data then
		data.folder:Destroy()
		resetGarage(data.slot) -- the garage stays: back to a new Garage, with no name on it
		plotOwners[data.slot] = nil
		playerData[player] = nil
	end
end)
''',
     '''	data.ready = true -- the shop waits for this before granting purchases

	setGarageState(slot, "Taken", player.DisplayName)
	player.CharacterAdded:Connect(function(character)
		teleportToPlot(character, slot)
	end)
	if player.Character then
		task.spawn(teleportToPlot, player.Character, slot)
	end
end

-- What LobbyConfig.canClaim needs, read from the server's own tables as they are now
local function claimState()
	local owners = {}
	for slot, owner in pairs(plotOwners) do
		owners[slot] = { name = owner.DisplayName, closing = garageState[slot] == "Closing" }
	end
	return { enabled = LobbyConfig.ClaimEnabled, count = MAX_PLOTS, owners = owners, claims = claims, lastAsk = lastClaimAsk }
end

-- A claim from a garage's prompt. The client only holds the prompt: the garage is the prompt's own and the distance is
-- measured here. The check and the claim run with no yield in between, so of two requests at once the first wins.
requestClaim = function(player, slot)
	if not inPlaza[player] then return end -- already moving in or playing, or gone
	local now = os.clock()
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	local post = claimPart(slot, "ClaimPost")
	local distance = root and post and (root.Position - post.Position).Magnitude or nil
	local ok, reason = LobbyConfig.canClaim(claimState(), { userId = player.UserId, slot = slot, distance = distance, now = now })
	lastClaimAsk[player.UserId] = now
	if not ok then
		ShopServer.notify(player, reason)
		return
	end
	claimGarage(player, slot)
end

-- ClaimEnabled off: the server claims the first free garage for a joining player and sends them in, as before. With none
-- free (one is closing: its leave save still runs) or this account's last visit still saving, they wait on the plaza
-- and it tries every second; after LobbyConfig.AutoClaimWait seconds, the old "server is full" kick.
local function autoClaim(player)
	local waited = 0
	while player.Parent and inPlaza[player] do
		for slot = 1, MAX_PLOTS do
			if LobbyConfig.canClaim(claimState(), { userId = player.UserId, slot = slot, auto = true }) then
				claimGarage(player, slot)
				return
			end
		end
		if waited >= LobbyConfig.AutoClaimWait then
			player:Kick(LobbyConfig.Texts.Full)
			return
		end
		task.wait(1)
		waited += 1
	end
end

-- The claim on: a spawn far from the plaza (the SpawnLocation was not moved there) is put on the plaza
local function toPlaza(player, character)
	if not (LobbyConfig.ClaimEnabled and inPlaza[player]) then return end
	local root = character:WaitForChild("HumanoidRootPart", 5)
	if not (root and inPlaza[player]) then return end
	local c = LobbyConfig.PlazaCenter
	local dx, dz = root.Position.X - c.x, root.Position.Z - c.z
	if math.sqrt(dx * dx + dz * dz) > LobbyConfig.PlazaRadius then
		local s = LobbyConfig.PlazaSpawn
		root.CFrame = CFrame.new(s.x, s.y, s.z)
	end
end

-- Joining: the player only enters the plaza. inPlaza is written before anything can yield, so the check below for players
-- who joined while this script was starting never sets anyone up twice. Nothing is read or saved before a claim.
local function onPlayerAdded(player)
	if inPlaza[player] or playerData[player] then return end -- already here: the startup loop and PlayerAdded both called
	inPlaza[player] = true
	player:SetAttribute("Garage", 0) -- 0 = no garage yet (LobbyClient, the shop's Robux buttons)
	if #Players:GetPlayers() > MAX_PLOTS then
		player:Kick(LobbyConfig.Texts.Full) -- more players than garages (Max Players above 6)
		return
	end
	player.CharacterAdded:Connect(function(character)
		toPlaza(player, character)
	end)
	if player.Character then
		task.spawn(toPlaza, player, player.Character)
	end
	if not LobbyConfig.ClaimEnabled then
		autoClaim(player)
	end
end
Players.PlayerAdded:Connect(onPlayerAdded)
-- Players already in the server (they joined while this script was still starting) are set up too
for _, existing in ipairs(Players:GetPlayers()) do
	if not inPlaza[existing] and not playerData[existing] then
		task.spawn(onPlayerAdded, existing)
	end
end

-- Leaving: the garage shows Closing while the leave save runs (the slot stays taken, FR-3). When it returns, the owner's
-- things go, the garage is a new Garage again (Free), and only then may this account claim again: a rejoin from another
-- device waits for it, so its load reads this save.
Players.PlayerRemoving:Connect(function(player)
	inPlaza[player] = nil
	local data = playerData[player]
	local held = claims[player.UserId]
	if data then
		setGarageState(data.slot, "Closing", player.DisplayName)
		if held then held.leaving = true end
	end
	saveOnLeave(player)
	if data then
		data.folder:Destroy()
		resetGarage(data.slot) -- the garage stays: back to a new Garage, Free, with no name on it
		plotOwners[data.slot] = nil
		playerData[player] = nil
		claimedAt[player] = nil
		if claims[player.UserId] == held then
			claims[player.UserId] = nil
		end
	end
end)
'''),
)


# PR L4's edits outside the CLAIMLOAD markers (the ring and the plaza, only with ClaimEnabled on), applied after L3_EDITS
L4_EDITS = (
    # the garages' turns: the ring's while the claim is on
    ('''local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }
''',
     '''local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }
if LobbyConfig.ClaimEnabled then -- the ring (lobby L4): each garage turned to face the plaza (LobbyConfig.Ring)
	for slot, g in ipairs(LobbyConfig.Garages) do
		GARAGE_TURNS[slot] = g.turn
	end
end
'''),
    # plotCenter: the ring's centers while the claim is on (the row otherwise)
    ('''local function plotCenter(slot)
	local startX = -((MAX_PLOTS - 1) * PLOT_SPACING) / 2
''',
     '''local function plotCenter(slot)
	if LobbyConfig.ClaimEnabled then -- the ring around the plaza (lobby L4); with the claim off, the row as always
		local g = LobbyConfig.Garages[slot]
		return Vector3.new(g.x, 0.5, g.z)
	end
	local startX = -((MAX_PLOTS - 1) * PLOT_SPACING) / 2
'''),
    # the landing asks streaming for the garage first
    ('''	local signPos = plotFrame(slot) * Vector3.new(0, 4, 24)
	root.CFrame = CFrame.lookAt(spawnPos, signPos)
''',
     '''	local signPos = plotFrame(slot) * Vector3.new(0, 4, 24)
	local player = Players:GetPlayerFromCharacter(character)
	if player then
		pcall(player.RequestStreamAroundAsync, player, spawnPos) -- streaming: the garage is there before they land (lobby L4)
	end
	root.CFrame = CFrame.lookAt(spawnPos, signPos)
'''),
    # the plaza world, built once at server start, only with the claim on
    ('''buildGarages()

''',
     '''buildGarages()

-- The plaza and the decor around the ring (lobby L4): WorldVisuals draws it once from WorldArt, only with the claim on
-- (with it off the garages stand in the row, as always, and there is no world). Looks only, inside pcall.
if LobbyConfig.ClaimEnabled then
	local worldOk, WorldVisuals = pcall(require, script.Parent:WaitForChild("WorldVisuals", 5))
	local worldArtOk, WorldArt = pcall(require, script.Parent:WaitForChild("WorldArt", 5))
	local drawn, problem = false, tostring(worldOk and WorldArt or WorldVisuals)
	if worldOk and worldArtOk then
		drawn, problem = pcall(function()
			local site = WorldVisuals.ringSite(WorldArt, LobbyConfig.Garages)
			return WorldVisuals.build(workspace, WorldArt, site)
		end)
	end
	if not drawn then
		warn("The plaza is off: " .. tostring(problem))
	end
end

'''),
)


def with_l1_edits(base):
    """BASE's TycoonCore.lua (bytes) with L1_EDITS to L4_EDITS applied, or None when an old text is not there exactly once."""
    text = base.decode("utf-8")
    for old, new in L1_EDITS + L2_EDITS + L3_EDITS + L4_EDITS:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text.encode("utf-8")


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def read_bytes(name):
    with open(os.path.join(ROOT, name), "rb") as f:
        return f.read()


def git_show(rev, path):
    """The bytes of path at rev, or None if git or the commit is missing."""
    try:
        got = subprocess.run(["git", "show", "%s:%s" % (rev, path)], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    return got.stdout if got.returncode == 0 else None


def run_luau(luau, source):
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        return subprocess.run([luau, path], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(path)


def lua_long_string(text):
    level = 0
    while ("]" + "=" * level + "]") in text:
        level += 1
    return "[" + "=" * level + "[\n" + text + "]" + "=" * level + "]"


def marker_lines(lines, marker):
    """Indexes (0-based) of the lines that hold marker."""
    return [i for i, line in enumerate(lines) if marker.encode() in line]


def marked_block(lines):
    """The lines strictly between the one START line and the one END line, each with its newline, or None."""
    starts, ends = marker_lines(lines, START), marker_lines(lines, END)
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        return None
    return b"".join(line + b"\n" for line in lines[starts[0] + 1:ends[0]])


def checks(core, base, doc, others=None):
    """[(name, ok, extra)] for TycoonCore.lua's bytes (core), the file at BASE (base, or None), the sync doc, and the
    bytes of L1's other four scripts (others: {name: bytes}, read from the folder when None)."""
    out = []

    def add(name, ok, extra=None):
        out.append((name, bool(ok), extra))

    lines = core.split(b"\n")
    base_lines = base.split(b"\n") if base is not None else []
    add("git: TycoonCore.lua at %s can be read (git show %s:TycoonCore.lua; a shallow clone may lack it)" % (BASE, BASE),
        base is not None)
    add("base: at %s, line %d is the save read (local saved, ok = load(player)) and line %d sets data.ready" % (BASE, FIRST, LAST),
        len(base_lines) > LAST and base_lines[FIRST - 1] == b"\tlocal saved, ok = load(player)"
        and base_lines[LAST - 1].startswith(b"\tdata.ready = true"))
    add("base: TycoonCore.lua at %s has no CLAIMLOAD text" % BASE, base is not None and b"CLAIMLOAD" not in base)

    starts, ends = marker_lines(lines, START), marker_lines(lines, END)
    add("markers: exactly one CLAIMLOAD-START line and one CLAIMLOAD-END line, START first",
        len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0], (len(starts), len(ends)))
    add("markers: each marker line is a tab and the marker, nothing else",
        all(lines[i] == b"\t" + START.encode() for i in starts) and all(lines[i] == b"\t" + END.encode() for i in ends))
    head = next((i for i, line in enumerate(lines) if line == b"local function claimGarage(player, slot)"), None)
    tail = next((i for i, line in enumerate(lines) if line == b"local function claimState()"), None)
    add("markers: both are inside claimGarage (after its first line, before the next function, claimState; PR L3 made the join's load the claim's)",
        head is not None and tail is not None and starts and ends and all(head < i < tail for i in starts + ends))

    block = marked_block(lines)
    want = b"".join(line + b"\n" for line in base_lines[FIRST - 1:LAST]) if len(base_lines) > LAST else None
    add("block: the text between the CLAIMLOAD markers is lines %d-%d of TycoonCore.lua at %s, byte for byte" % (FIRST, LAST, BASE),
        block is not None and want is not None and block == want,
        None if block is None or want is None else "%d bytes, want %d" % (len(block), len(want)))

    named = [line for line in lines if b"CLAIMLOAD" in line]
    add("outside: every line that names CLAIMLOAD is a comment line (no code hides on one)",
        all(line.lstrip(b"\t ").startswith(b"--") for line in named), [line[:60] for line in named])
    stripped = b"\n".join(line for line in lines if b"CLAIMLOAD" not in line)
    edited = with_l1_edits(base) if base is not None else None
    add("outside: L1's %d plot-frame edits and L2's %d building edits each apply once to TycoonCore.lua at %s (their old text is there exactly once)"
        % (len(L1_EDITS), len(L2_EDITS), BASE), edited is not None)
    add("outside: TycoonCore.lua without its CLAIMLOAD comment lines is TycoonCore.lua at %s plus L1's plot-frame edits and L2's building "
        "edits, byte for byte (L0 adds comments only, L1 and L2 only their listed edits)" % BASE, edited is not None and stripped == edited)
    add("file: TycoonCore.lua has no word \"Touched\", comments included (tools/daily_test.py searches the raw text)",
        b"Touched" not in core)

    section = l1_section(doc)
    add("doc: %s has the L1 section (%s)" % (SYNC_DOC, L1_HEADING), bool(section))
    files = dict(others if others is not None else l1_others())
    for name, cls, place in L1_SCRIPTS:
        body = files.get(name)
        digest = hashlib.sha256(body).hexdigest() if body is not None else "missing"
        size = len(body) if body is not None else -1
        add("doc: %s's L1 table row has %s.lua's real SHA-256 and size (%s, %d bytes)" % (SYNC_DOC, name, digest[:12], size),
            ("| `%s` | %s, %s | changed | `%s` | %d |" % (name, cls, place, digest, size)) in section)
        add("doc: %s's L1 hash block expects %s.lua's real SHA-256 and size" % (SYNC_DOC, name),
            ('{ "%s", "%s", "%s", "%s", %d },' % (name, cls, place, digest, size)) in section)

    # The Lobby all section (history): every script lobby-all creates or changes, at its hash when lobby-all merged
    current = doc_section(doc, ALL_HEADING)
    add("doc: %s has the section %s" % (SYNC_DOC, ALL_HEADING), bool(current))
    now = all_files()
    lacking = [name for name, _, _, _ in ALL_SCRIPTS if name not in now]
    add("git: lobby-all's scripts can be read at %s (git show; a copy without the git history or a shallow clone lacks them)" % ALL_COMMIT,
        not lacking, ", ".join(lacking) or None)
    for name, cls, place, state in ALL_SCRIPTS:
        body = now.get(name)
        digest = hashlib.sha256(body).hexdigest() if body is not None else "missing"
        size = len(body) if body is not None else -1
        add("doc: %s's Lobby all table row has %s.lua's real SHA-256 and size (%s, %d bytes)" % (SYNC_DOC, name, digest[:12], size),
            ("| `%s` | %s, %s | %s | `%s` | %d |" % (name, cls, place, state, digest, size)) in current)
        add("doc: %s's Lobby all hash block expects %s.lua's real SHA-256 and size" % (SYNC_DOC, name),
            ('{ "%s", "%s", "%s", "%s", %d },' % (name, cls, place, digest, size)) in current)
    return out


def doc_section(doc, heading):
    """docs/STUDIO_SYNC_LOBBY.md from heading to the next "## " heading (or the end), or "" when it is missing."""
    at = doc.find(heading)
    if at < 0:
        return ""
    nxt = doc.find("\n## ", at + len(heading))
    return doc[at:nxt if nxt >= 0 else len(doc)]


def all_files():
    """{name: bytes} of the scripts lobby-all creates or changes, as lobby-all merged them into main (ALL_COMMIT; missing
    ones left out): the Lobby all section is history, like the L1 section."""
    out = {}
    for name, _, _, _ in ALL_SCRIPTS:
        body = git_show(ALL_COMMIT, name + ".lua")
        if body is not None:
            out[name] = body
    return out


def l1_section(doc):
    """docs/STUDIO_SYNC_LOBBY.md from the L1 heading to the next PR heading (or the end), or "" when it is missing."""
    at = doc.find(L1_HEADING)
    if at < 0:
        return ""
    nxt = doc.find("\n## L", at + len(L1_HEADING))
    return doc[at:nxt if nxt >= 0 else len(doc)]


def l1_others():
    """{name: bytes} of L1's five scripts as L1 merged them into main (L1_COMMIT): the L1 section is history."""
    out = {}
    for name, _, _ in L1_SCRIPTS:
        body = git_show(L1_COMMIT, name + ".lua")
        if body is not None:
            out[name] = body
    return out


def lua_block(doc, heading):
    """The first ```lua block after heading in doc, or "" if there is none."""
    at = doc.find(heading)
    if at < 0:
        return ""
    m = re.search(r"```lua\n(.*?)```", doc[at:], re.S)
    return m.group(1) if m else ""


FAKE_STUDIO = """
local function folder(scripts) return { FindFirstChild = function(_, name) return scripts[name] end } end
local server = folder({ __SERVER__ })
local shared = folder({ __SHARED__ })
local playerScripts = folder({ __CLIENT__ })
local starterPlayer = { FindFirstChild = function(_, name) if name == "StarterPlayerScripts" then return playerScripts end return nil end }
game = { GetService = function(_, name)
	if name == "ServerScriptService" then return server elseif name == "StarterPlayer" then return starterPlayer
	elseif name == "ReplicatedStorage" then return shared end
	return nil
end }
"""


def fake_studio(sources, scripts=None):
    """The fake Studio holding scripts ({name: source text}) with their classes and places (default: L1's five)."""
    server, client, shared = [], [], []
    for name, cls, place in (scripts or L1_SCRIPTS):
        if name not in sources:
            continue
        entry = "%s = { ClassName = \"%s\", Source = %s }" % (name, cls, lua_long_string(sources[name]))
        (client if place == "StarterPlayerScripts" else shared if place == "ReplicatedStorage" else server).append(entry)
    return FAKE_STUDIO.replace("__SERVER__", ", ".join(server)).replace("__CLIENT__", ", ".join(client)).replace("__SHARED__", ", ".join(shared))


def hash_block_checks(luau, core, doc):
    """docs/STUDIO_SYNC_LOBBY.md's L1 hash block, run in Luau against a fake Studio holding L1's five scripts."""
    out = []
    block = lua_block(l1_section(doc), "### (c) Hash check (command bar)")
    master = lua_block(read("docs/STUDIO_SYNC_MASTER.md"), "## 6. Hash check (command bar)")
    fn = re.compile(r"^local K = \{.*?\nend\n", re.S)
    mine, theirs = fn.search(block), fn.search(master)
    out.append(("doc: the hash block's sha256 is docs/STUDIO_SYNC_MASTER.md section 6's, character for character",
                bool(mine and theirs and mine.group(0) == theirs.group(0)), None))
    real = {name: body.decode("utf-8") for name, body in l1_others().items()}
    lacking = [name for name, _, _ in L1_SCRIPTS if name not in real]
    out.append(("git: L1's five scripts can be read at %s (git show; a copy without the git history or a shallow clone lacks them)" % L1_COMMIT,
                not lacking, ", ".join(lacking) or None))
    cases = ()
    if not lacking:
        dropped = {name: text[:-1] for name, text in real.items()}
        client = dict(real)
        client["EmployeeClient"] = client["EmployeeClient"].replace("local walkers = {}", "local walkers = { }", 1)
        server = dict(real)
        server["TycoonCore"] = server["TycoonCore"].replace("REREAD_WAIT_SECONDS = 7", "REREAD_WAIT_SECONDS = 8", 1)
        cases = (("the five real files", real, "ALL OK"),
                 ("the five real files with their last newline dropped (Studio may do that)", dropped, "ALL OK"),
                 ("TycoonCore with one byte changed", server, "NOT YET"),
                 ("EmployeeClient (in StarterPlayerScripts) with one byte changed", client, "NOT YET"))
    for label, sources, want in cases:
        result = run_luau(luau, fake_studio(sources) + block)
        last = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else result.stderr.strip()[:200]
        out.append(("doc: the L1 hash block, run in Luau on a fake Studio with %s, ends with %s" % (label, want),
                    result.returncode == 0 and last.startswith(want), last))

    # The Lobby all block, on the real files (TycoonCore as given), then with one byte changed, then with one missing
    block = lua_block(doc_section(doc, ALL_HEADING), "### 4. Hash check (command bar)")
    mine = fn.search(block)
    out.append(("doc: the Lobby all hash block's sha256 is docs/STUDIO_SYNC_MASTER.md section 6's, character for character",
                bool(mine and theirs and mine.group(0) == theirs.group(0)), None))
    scripts = [(name, cls, place) for name, cls, place, _ in ALL_SCRIPTS]
    now = {name: body.decode("utf-8") for name, body in all_files().items()}
    changed = dict(now)
    changed["BuildingClient"] = changed["BuildingClient"].replace("local TAG = ", "local  TAG = ", 1)
    missing = {name: text for name, text in now.items() if name != "PlotBuilding"}
    cases = (("every real file", now, "ALL OK"), ("every real file with its last newline dropped", {n: s[:-1] for n, s in now.items()}, "ALL OK"),
             ("BuildingClient (in StarterPlayerScripts) with one byte changed", changed, "NOT YET"), ("PlotBuilding missing", missing, "NOT YET"))
    for label, sources, want in cases:
        result = run_luau(luau, fake_studio(sources, scripts) + block)
        last = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else result.stderr.strip()[:200]
        out.append(("doc: the Lobby all hash block, run in Luau on a fake Studio with %s, ends with %s" % (label, want),
                    result.returncode == 0 and last.startswith(want), last))
    return out


def ins_after(anchor, text):
    def apply(core):
        if core.count(anchor) != 1:
            return None
        return core.replace(anchor, anchor + text)
    return apply


def swap(old, new):
    def apply(core):
        if core.count(old) != 1:
            return None
        return core.replace(old, new)
    return apply


def move(piece, before):
    """Removes piece and puts it again just before the anchor before."""
    def apply(core):
        if core.count(piece) != 1:
            return None
        rest = core.replace(piece, "")
        if rest.count(before) != 1:
            return None
        return rest.replace(before, piece + before)
    return apply


LEFT_LOADING = "\tif playerData[player] ~= data then return end -- they left while loading: nothing was saved\n"
LEADERSTATS = ('\tlocal leaderstats = Instance.new("Folder")\n\tleaderstats.Name = "leaderstats"\n\tleaderstats.Parent = player\n\n'
               '\tlocal cash = Instance.new("IntValue")\n\tcash.Name = "Cash"\n\tcash.Parent = leaderstats\n\n'
               '\tlocal income = Instance.new("IntValue")\n\tincome.Name = "Income"\n\tincome.Parent = leaderstats\n\n')
BLOCK_CHECK = "block: the text between the CLAIMLOAD markers is lines %d-%d of TycoonCore.lua at %s, byte for byte" % (FIRST, LAST, BASE)
OUTSIDE_CHECK = "outside: TycoonCore.lua without its CLAIMLOAD comment lines is TycoonCore.lua at %s plus L1's plot-frame edits and L2's building edits" % BASE
EDITS_CHECK = "outside: L1's %d plot-frame edits and L2's %d building edits each apply once" % (len(L1_EDITS), len(L2_EDITS))
COUNT_CHECK = "markers: exactly one CLAIMLOAD-START line and one CLAIMLOAD-END line, START first"
SHAPE_CHECK = "markers: each marker line is a tab and the marker, nothing else"
PLACE_CHECK = "markers: both are inside claimGarage"
COMMENT_CHECK = "outside: every line that names CLAIMLOAD is a comment line (no code hides on one)"

# (what is broken, how, the start of the named check that must fail)
MUTANTS = [
    # The proposal's section 2.1 set: in L0 the byte compare is what catches each one (L3 also runs the block)
    ("the \"left while loading\" check after the read (:775) is removed",
     swap("load(player)\n" + LEFT_LOADING + "\tok = readableSave", "load(player)\n\tok = readableSave"), BLOCK_CHECK),
    ("the \"left while waiting\" check after the re-read wait (:788) is removed",
     swap("\t\ttask.wait(REREAD_WAIT_SECONDS)\n\t\tif playerData[player] ~= data then return end -- they left while waiting: nothing was saved\n",
          "\t\ttask.wait(REREAD_WAIT_SECONDS)\n"), BLOCK_CHECK),
    ("the check after the second read (:790) is removed",
     swap("local again, againOk = load(player)\n\t\tif playerData[player] ~= data then return end\n", "local again, againOk = load(player)\n"),
     BLOCK_CHECK),
    ("the \"left while loading\" check after the setup pcall (:833) is removed",
     swap("\tend)\n" + LEFT_LOADING + "\tif not setupOk", "\tend)\n\tif not setupOk"), BLOCK_CHECK),
    ("data.loaded = ok moved above the check after the setup pcall (:833)",
     move("\tdata.loaded = ok -- from here on, saves are complete\n", "\tend)\n" + LEFT_LOADING), BLOCK_CHECK),
    ("data.loaded = true instead of ok", swap("\tdata.loaded = ok -- from", "\tdata.loaded = true -- from"), BLOCK_CHECK),
    ("leaderstats made after load (the folder and its two values moved below the read)",
     move(LEADERSTATS, "\tif playerData[player] ~= data then return end -- they left while loading: nothing was saved\n\tok = readableSave"),
     BLOCK_CHECK),
    # Spacing inside the block
    ("a line of the block indented with four spaces instead of a tab", swap("\tok = readableSave(", "    ok = readableSave("), BLOCK_CHECK),
    ("a trailing space after refreshSign(player) in the block", swap("\trefreshSign(player)\n\tdata.ready", "\trefreshSign(player) \n\tdata.ready"),
     BLOCK_CHECK),
    ("a CRLF line ending in the block", swap("\tupdateIncome(player)\n\n\t-- Offline", "\tupdateIncome(player)\r\n\n\t-- Offline"), BLOCK_CHECK),
    ("an empty line added inside the block", swap("\tlocal lastSeen = nil\n", "\tlocal lastSeen = nil\n\n"), BLOCK_CHECK),
    # The markers themselves
    ("the START marker one line lower (the read is left outside)",
     swap("\t" + START + "\n\tlocal saved, ok = load(player)\n", "\tlocal saved, ok = load(player)\n\t" + START + "\n"), BLOCK_CHECK),
    ("the END marker one line higher (data.ready is left outside)",
     swap("\tdata.ready = true -- the shop waits for this before granting purchases\n\t" + END + "\n",
          "\t" + END + "\n\tdata.ready = true -- the shop waits for this before granting purchases\n"), BLOCK_CHECK),
    ("a second START marker pasted lower in the block", ins_after("\tlocal lastSeen = nil\n", "\t" + START + "\n"), COUNT_CHECK),
    ("the END marker removed", swap("\t" + END + "\n", ""), COUNT_CHECK),
    ("the markers swapped (END first)",
     lambda core: core.replace("\t" + START + "\n", "\t@@S@@\n").replace("\t" + END + "\n", "\t" + START + "\n").replace("\t@@S@@\n", "\t" + END + "\n")
     if core.count("\t" + START + "\n") == 1 and core.count("\t" + END + "\n") == 1 else None, COUNT_CHECK),
    ("text after the START marker on its line", swap("\t" + START + "\n", "\t" + START + " (the join load)\n"), SHAPE_CHECK),
    ("the END marker moved below Players.PlayerAdded:Connect",
     move("\t" + END + "\n", "for _, existing in ipairs(Players:GetPlayers()) do\n"), PLACE_CHECK),
    ("the END marker moved into requestClaim (after claimGarage)",
     move("\t" + END + "\n", "\tlastClaimAsk[player.UserId] = now\n"), PLACE_CHECK),
    # Outside the block
    ("code hidden on a CLAIMLOAD line outside the block (data.loaded = true -- CLAIMLOAD)",
     ins_after("\t" + END + "\n", "\tdata.loaded = true -- CLAIMLOAD\n"), COMMENT_CHECK),
    ("an edit outside the markers (REREAD_WAIT_SECONDS = 7 becomes 0)",
     swap("local REREAD_WAIT_SECONDS = 7\n", "local REREAD_WAIT_SECONDS = 0\n"), OUTSIDE_CHECK),
    # (No mutant for a comment-only edit of TycoonCore any more: the Lobby all section is history, checked against
    # ALL_COMMIT, so a later edit of TycoonCore never makes its hash stale. Ux lane request R1, 2026-10-17.)
    # PR L1: only its listed plot-frame edits outside the markers, and none inside
    ("L1: the room line inside the block given the frame (plotFrame(slot) instead of plotCenter(slot))",
     swap("PlotVisuals.newPlot, folder, plotCenter(slot), PlotArt", "PlotVisuals.newPlot, folder, plotFrame(slot), PlotArt"), BLOCK_CHECK),
    ("L1: a garage turned (GARAGE_TURNS with a 90)", swap("local GARAGE_TURNS = { 0, 0, 0, 0, 0, 0 }", "local GARAGE_TURNS = { 0, 0, 0, 90, 0, 0 }"),
     OUTSIDE_CHECK),
    ("L1: the landing put back on plotCenter (an edit not in L1's list)",
     swap("\tlocal spawnPos = plotFrame(slot) * Vector3.new(0, 4, 12)\n", "\tlocal spawnPos = plotCenter(slot) + Vector3.new(0, 4, 12)\n"), OUTSIDE_CHECK),
    ("L1: PoachServer's core given plotFrame too (a third core table edited)",
     swap("\tplotCenter = plotCenter,\n\tpeekSave = peekSave,\n", "\tplotFrame = plotFrame,\n\tpeekSave = peekSave,\n"), OUTSIDE_CHECK),
    ("L1: a comment line of the frame reworded (the doc's hash goes stale and the edit list no longer matches)",
     swap("-- garage stands as it always has", "-- garage stands where it always stood"), OUTSIDE_CHECK),
    # PR L2: only its listed building edits outside the markers, and none inside
    ("L2: the building synced inside the CLAIMLOAD block (building-pass's third edit, which L2 drops)",
     ins_after("	data.looks = PlotVisuals and looks(\"room\", PlotVisuals.newPlot, folder, plotCenter(slot), PlotArt, floor, stageOf(data))\n",
               "	syncBuilding(slot, stageOf(data))\n"), BLOCK_CHECK),
    ("L2: no reset on leave (the garage keeps the old owner's building and name)",
     swap("\t\tresetGarage(data.slot) -- the garage stays: back to a new Garage, Free, with no name on it\n", ""), OUTSIDE_CHECK),
    ("L2: a label per owner (the join adds a billboard on the Floor again)",
     swap("\tsetGarageSign(slot, player.DisplayName .. \"'s Startup\")\n", "\taddLabel(floor, player.DisplayName .. \"'s Startup\", 12)\n"), OUTSIDE_CHECK),
    ("L2: the building required without pcall (a broken building module would stop the game)",
     swap("local buildingOk, PlotBuildingVisuals = pcall(require, script.Parent:WaitForChild(\"PlotBuildingVisuals\", 5))",
          "local buildingOk, PlotBuildingVisuals = true, require(script.Parent:WaitForChild(\"PlotBuildingVisuals\"))"), OUTSIDE_CHECK),
    ("L2: the Floor made per join again (a second Floor in the owner's folder)",
     swap("\tlocal floor = garages[slot].Floor -- permanent (buildGarages): the room takes its turn from it\n",
          "\tlocal floor = makePart(folder, \"Floor\", Vector3.new(60, 1, 60), plotFrame(slot), Color3.fromRGB(90, 90, 100))\n"), OUTSIDE_CHECK),
]

# The harness must report this as not caught: the checks crash on it (the file is not text), and a crash never counts.
HARNESS_SELF_TEST = ("a mutant that makes the checks crash (TycoonCore.lua is not text)", lambda core: 0, BLOCK_CHECK)


def run_one(core_text, apply, base, doc):
    """(checks, error): the checks for the mutated file, or the error that stopped them (a crash)."""
    mutated = apply(core_text)
    if mutated is None:
        return None, "not applied: its anchor is missing or there twice"
    try:
        return checks(mutated.encode("utf-8"), base, doc), None
    except Exception as e:  # a crash is never a catch
        return None, "it crashed: %s: %s" % (type(e).__name__, e)


def run_mutants(core_text, base, doc, mutants=MUTANTS):
    caught, lines = 0, []
    names = [name for name, _, _ in checks(core_text.encode("utf-8"), base, doc)]
    for label, apply, want in mutants:
        if not any(name.startswith(want) for name in names):
            lines.append("NOT CAUGHT: %s -- no check is named \"%s\"" % (label, want))
            continue
        result, error = run_one(core_text, apply, base, doc)
        if error:
            lines.append("NOT CAUGHT: %s -- %s" % (label, error))
            continue
        failed = [name for name, ok, _ in result if not ok]
        if any(name.startswith(want) for name in failed):
            caught += 1
            lines.append("caught: %s -- by \"%s\"" % (label, next(n for n in failed if n.startswith(want))))
        else:
            lines.append("NOT CAUGHT: %s -- \"%s\" stayed green (failed: %s)" % (label, want, failed))
    return caught, lines


# --- PR L3: the whole TycoonCore run in a fake Roblox (tools/lobby_runtime.luau) -----------------------------------------
RUNTIME_FILE = os.path.join("tools", "lobby_runtime.luau")
HOOKS = ("\n\treturn { playerData = playerData, plotOwners = plotOwners, claims = claims, inPlaza = inPlaza, garageState = garageState, "
         "claimedAt = claimedAt }\nend\n")


FAKE_ARGS = "game, script, workspace, task, os, warn, require, newInstance, Enum, Vector3, CFrame, Color3, UDim2, typeof"


def runtime_program(sources):
    """The runtime test program for {file: text} (TycoonCore.lua, LobbyConfig.lua, IpoConfig.lua, ShopServer.lua,
    ShopConfig.lua): each real script runs as a function of the fake Roblox's globals."""
    body = read(RUNTIME_FILE)
    boot = ("local function BOOT_CORE(" + FAKE_ARGS + ")\n\tlocal Instance = { new = newInstance }\n" + sources["TycoonCore.lua"] + HOOKS)
    shop = ("local function SHOP_SOURCE(" + FAKE_ARGS + ")\n\tlocal Instance = { new = newInstance }\n" + sources["ShopServer.lua"] + "\nend\n")
    mods = ("local LOBBY_SOURCE = function()\n" + sources["LobbyConfig.lua"] + "\nend\n"
            "local IPOCONFIG_SOURCE = function()\n" + sources["IpoConfig.lua"] + "\nend\n"
            "local SHOPCONFIG_SOURCE = function()\n" + sources["ShopConfig.lua"] + "\nend\n")
    at = body.index("-- One world:")
    return body[:at] + boot + shop + mods + body[at:]


def runtime_checks(luau, sources):
    """[(name, ok, extra)] of the runtime program; a crash or a missing DONE is one failed check of its own."""
    result = run_luau(luau, runtime_program(sources))
    out = []
    for line in result.stdout.splitlines():
        if line.startswith("FAIL: "):
            name, _, extra = line[len("FAIL: "):].partition(" -- ")
            out.append((name, False, extra or None))
    m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
    for _ in range(int(m.group(1)) if m else 0):
        out.append(("runtime", True, None))
    if result.returncode != 0 or "DONE" not in result.stdout.splitlines():
        out.append(("runtime: the program ran to the end (it crashed: a crash is never a catch)", False, (result.stderr or result.stdout)[-300:]))
    return out


def runtime_sources():
    return {name: read(name) for name in ("TycoonCore.lua", "LobbyConfig.lua", "IpoConfig.lua", "ShopServer.lua", "ShopConfig.lua")}


# (what is broken, file, old, new, the start of the named runtime check that must fail)
L3_MUTANTS = [
    ("no one-claim check (canClaim forgets the account's held claim)", "LobbyConfig.lua", "\tlocal held = state.claims[request.userId]\n\tif held then",
     "\tlocal held = state.claims[request.userId]\n\tif false then", "rejoin: while the old visit is still saving"),
    ("the claim keyed on the Player, not the UserId", "TycoonCore.lua", "\tclaims[player.UserId] = { slot = slot }\n", "\tclaims[player] = { slot = slot }\n", "rejoin: while the old visit"),
    ("the claim released before the leave save returns", "TycoonCore.lua", "\tinPlaza[player] = nil\n\tlocal data = playerData[player]\n\tlocal held = claims[player.UserId]\n",
     "\tinPlaza[player] = nil\n\tlocal data = playerData[player]\n\tlocal held = claims[player.UserId]\n\tclaims[player.UserId] = nil\n", "rejoin: while the old visit"),
    ("a yield between the check and the claim", "TycoonCore.lua", "\tif not ok then\n\t\tShopServer.notify(player, reason)\n\t\treturn\n\tend\n\tclaimGarage(player, slot)\n",
     "\tif not ok then\n\t\tShopServer.notify(player, reason)\n\t\treturn\n\tend\n\ttask.wait()\n\tclaimGarage(player, slot)\n", "two claims in one moment"),
    ("the plaza marker written after a yield (and no already-here check: the plan's own case)", "TycoonCore.lua",
     "\tif inPlaza[player] or playerData[player] then return end -- already here: the startup loop and PlayerAdded both called\n\tinPlaza[player] = true\n",
     "\ttask.wait()\n\tinPlaza[player] = true\n", "early joiner"),
    ("onPlayerAdded runs twice for one player (no already-here check)", "TycoonCore.lua", "\tif inPlaza[player] or playerData[player] then return end -- already here: the startup loop and PlayerAdded both called\n",
     "", "early joiner"),
    ("leaderstats made on the join (before the claim)", "TycoonCore.lua", "\tplayer:SetAttribute(\"Garage\", 0) -- 0 = no garage yet (LobbyClient, the shop's Robux buttons)\n",
     "\tplayer:SetAttribute(\"Garage\", 0) -- 0 = no garage yet (LobbyClient, the shop's Robux buttons)\n\tlocal early = Instance.new(\"Folder\")\n\tearly.Name = \"leaderstats\"\n\tearly.Parent = player\n",
     "plaza: a joining player gets no garage"),
    ("no distance check", "LobbyConfig.lua", "\t\tif not finite(d) or d < 0 or d > LobbyConfig.ClaimDistance then", "\t\tif false then", "distance:"),
    ("the prompt left on for a Taken garage", "TycoonCore.lua", "\t\tif prompt then prompt.Enabled = free end\n", "\t\tif prompt then prompt.Enabled = LobbyConfig.ClaimEnabled end\n", "claim: the prompt goes off"),
    ("no reset on leave (the garage never Free again)", "TycoonCore.lua", "\t\tresetGarage(data.slot) -- the garage stays: back to a new Garage, Free, with no name on it\n", "", "leave: when the save returns"),
    ("the kill-switch path without the teleport", "TycoonCore.lua", "\tif player.Character then\n\t\ttask.spawn(teleportToPlot, player.Character, slot)\n\tend\nend\n\n-- What LobbyConfig.canClaim",
     "end\n\n-- What LobbyConfig.canClaim", "claim off: the player is sent into their garage"),
    ("the cap kicks at 6 players", "TycoonCore.lua", "\tif #Players:GetPlayers() > MAX_PLOTS then", "\tif #Players:GetPlayers() >= MAX_PLOTS then", "cap: six players"),
    ("the receipt deadline counted from the join", "ShopServer.lua", "\t\tif core.claimedAt then\n\t\t\tlocal claimed = core.claimedAt(player)\n\t\t\tif claimed and os.clock() >= claimed + DATA_WAIT_SECONDS then",
     "\t\tif core.claimedAt then\n\t\t\tlocal claimed = core.claimedAt(player)\n\t\t\tif os.clock() >= deadline then", "receipt: a player on the plaza"),
    ("the auto-claim kicks at once when every garage is taken (no wait for a closing one)", "TycoonCore.lua", "\t\tif waited >= LobbyConfig.AutoClaimWait then",
     "\t\tif waited >= 0 then", "claim off, all taken"),
    ("no plaza fallback (a far first spawn stays where it is)", "TycoonCore.lua", "\tif math.sqrt(dx * dx + dz * dz) > LobbyConfig.PlazaRadius then", "\tif false then", "plaza: a first spawn far"),
    ("the claim does not write plotOwners before the load (the garage looks free while moving in)", "TycoonCore.lua",
     "\tclaims[player.UserId] = { slot = slot }\n\tplotOwners[slot] = player\n", "\tclaims[player.UserId] = { slot = slot }\n", "two claims in one moment"),
    ("L4: the ring used while the claim is off (live players' garages would move)", "LobbyConfig.lua", "\treturn claimEnabled and LobbyConfig.Ring or LobbyConfig.Row",
     "\treturn LobbyConfig.Ring", "config: with the claim off the server uses the row"),
    ("L4: the ring's turns ignored (every garage facing +Z)", "TycoonCore.lua", "\t\tGARAGE_TURNS[slot] = g.turn\n", "", "load: the claim's player lands in their garage"),
    ("L4: plotCenter ignores the ring (the room in the row, the building in the ring)", "TycoonCore.lua",
     "\t\tlocal g = LobbyConfig.Garages[slot]\n\t\treturn Vector3.new(g.x, 0.5, g.z)\n", "\t\tlocal _ = LobbyConfig.Garages[slot]\n", "load: the claim's player lands in their garage"),
    ("the claim's rate check gone", "LobbyConfig.lua", "\t\tif last and finite(request.now) and request.now - last < LobbyConfig.ClaimInterval then", "\t\tif false then", "rate:"),
    # The receipt path (the real ShopServer with the real TycoonCore)
    ("ShopServer's waitForData without the data.ready check (a receipt granted on a save still loading)", "ShopServer.lua",
     "\t\tif data and data.ready then\n\t\t\treturn data\n", "\t\tif data then\n\t\t\treturn data\n", "receipt: after the claim, once the save has loaded"),
    ("ShopServer grants without data.loaded (a reward on a session that can never save)", "ShopServer.lua",
     "\tif not data or not data.loaded then\n", "\tif not data then\n", "receipt: a session whose save never loaded"),
    ("claimGarage never sets claimedAt (a receipt after the claim waits with no deadline)", "TycoonCore.lua", "\tclaimedAt[player] = os.clock()\n", "",
     "receipt: 30 s after the claim with the save still loading"),
    # The plaza, the income, the building, the claim spot
    ("inPlaza not cleared on leave", "TycoonCore.lua", "\tinPlaza[player] = nil\n\tlocal data = playerData[player]\n\tlocal held = claims[player.UserId]\n",
     "\tlocal data = playerData[player]\n\tlocal held = claims[player.UserId]\n", "leave: a player who leaves from the plaza"),
    ("passive income ignores data.ready (Cash paid while loading or while an IPO saves)", "TycoonCore.lua", "\t\t\tif stats and data.ready then\n",
     "\t\t\tif stats then\n", "income: while data.ready is off"),
    ("a broken building warns every second", "TycoonCore.lua", "\t\tif not buildingWarned then\n", "\t\tif true then\n", "building: a broken building warns once"),
    ("the claim spot streams like any model (not Persistent: a far post and its prompt are missing on the client)", "TycoonCore.lua",
     "\t\t\tspot.ModelStreamingMode = Enum.ModelStreamingMode.Persistent\n", "\t\t\tspot.ModelStreamingMode = Enum.ModelStreamingMode.Default\n",
     "plaza: each garage's claim post and lamp stand in its ClaimSpot"),
]


RAN_CHECK = "runtime: the program ran to the end"
# The harness must report this as not caught: TycoonCore errors as it starts, so the test program itself crashes.
RUNTIME_SELF_TEST = ("a mutant that makes TycoonCore error as it starts (the test program crashes)", "TycoonCore.lua",
                     "local MAX_PLOTS = 6\n", "local MAX_PLOTS = 6\nerror(\"crash (test)\")\n", "plaza:")


def run_l3_mutants(luau, mutants=None):
    base = runtime_sources()
    caught, lines = 0, []
    for label, file, old, new, want in (L3_MUTANTS if mutants is None else mutants):
        if base[file].count(old) != 1:
            lines.append("NOT CAUGHT: %s -- not applied (its anchor is missing or there twice)" % label)
            continue
        mutated = dict(base)
        mutated[file] = base[file].replace(old, new)
        failed = [name for name, ok, _ in runtime_checks(luau, mutated) if not ok]
        hit = [n for n in failed if n.startswith(want)]
        if any(n.startswith(RAN_CHECK) for n in failed):
            lines.append("NOT CAUGHT: %s -- the test program crashed (a crash is never a catch)" % label)
        elif hit:
            caught += 1
            lines.append("caught: %s -- by \"%s\"" % (label, hit[0]))
        else:
            lines.append("NOT CAUGHT: %s -- no failing check starts with \"%s\" (failed: %s)" % (label, want, failed[:3]))
    return caught, lines


CLIENT_TEST_FILE = os.path.join("tools", "lobby_client_test.luau")


def client_checks(luau, client_text=None, lobby_text=None):
    """[(name, ok, extra)] of the real LobbyClient.lua in a fake client (tools/lobby_client_test.luau)."""
    client = client_text if client_text is not None else read("LobbyClient.lua")
    lobby = lobby_text if lobby_text is not None else read("LobbyConfig.lua")
    head = ("local LOBBY_SOURCE = function()\n" + lobby + "\nend\n"
            "local CLIENT = function(game, workspace, Instance, require, UDim2, UDim, Color3, Enum, Vector3)\n" + client + "\nend\n")
    body = read(CLIENT_TEST_FILE)
    at = body.index("local function world(")
    result = run_luau(luau, body[:at] + head + body[at:])
    out = []
    for line in result.stdout.splitlines():
        if line.startswith("FAIL: "):
            name, _, extra = line[len("FAIL: "):].partition(" -- ")
            out.append((name, False, extra or None))
    m = re.search(r"(\d+) passed, (\d+) failed", result.stdout)
    out += [("client", True, None)] * (int(m.group(1)) if m else 0)
    if result.returncode != 0 or "DONE" not in result.stdout.splitlines():
        out.append(("client: the program ran to the end (it crashed: a crash is never a catch)", False, (result.stderr or result.stdout)[-300:]))
    return out


CLIENT_MUTANTS = [
    ("LobbyClient shows the banner with the claim off", "if not LobbyConfig.ClaimEnabled then\n\treturn -- the claim is off", "if false then\n\treturn -- the claim is off",
     "client: with the claim off"),
    ("LobbyClient marks a garage that is not Free", 'if post and garage:GetAttribute("State") == "Free" then', "if post then", "client: the marker is over the nearest FREE"),
    ("LobbyClient keeps the banner after the claim", "local show = onPlaza()", "local show = true", "client: with a garage the banner"),
    ("the marker put inside the banner's ScreenGui (a BillboardGui there never shows)", '\tParent = player:WaitForChild("PlayerGui"),\n})\nmake("TextLabel", {',
     '\tParent = gui,\n})\nmake("TextLabel", {', "client: the marker is a BillboardGui straight in PlayerGui"),
    ("the post looked for on the garage itself (not in its ClaimSpot: no marker ever)", 'local post = spot and spot:FindFirstChild("ClaimPost")',
     'local post = garage:FindFirstChild("ClaimPost")', "client: the marker is over the nearest FREE"),
]
CLEAN_CHECK = "client: ran without an error"
DONE_CHECK = "client: the program ran to the end"
# The harness must report this as not caught: the client errors on every frame, so checks about what it shows fail too,
# but a client that errored is never a catch (the separate "ran without an error" check fails).
CLIENT_SELF_TEST = ("a mutant that makes the client error on every frame", "\twaited += dt\n", "\twaited += dt\n\terror(\"crash (test)\")\n",
                    "client: the marker is over the nearest FREE")


def client_mutant_caught(luau, source, old, new, want):
    """(caught, why): a client mutant counts only when the client ran without an error in every scenario, the program
    ran to the end, and a check other than those two, starting with want, failed."""
    if source.count(old) != 1:
        return False, "not applied"
    result = client_checks(luau, source.replace(old, new))
    failed = [n for n, ok, _ in result if not ok]
    errored = [n for n in failed if n.startswith(CLEAN_CHECK) or n.startswith(DONE_CHECK)]
    if errored:
        return False, "the client errored (%s): an error is never a catch" % errored[0]
    if any(n.startswith(want) for n in failed):
        return True, None
    return False, "no failing check starts with \"%s\"" % want


def main():
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
        return 2
    core = read_bytes("TycoonCore.lua")
    base = git_show(BASE, "TycoonCore.lua")
    if base is None or git_show(L1_COMMIT, "TycoonCore.lua") is None:
        print("FAIL: this test needs the repo's git history (commits %s and %s), and git cannot read it here. Run it in a full clone "
              "of the repo (git clone, not a downloaded copy or a shallow clone); every check that needs that history fails below." % (BASE, L1_COMMIT))
    doc = read(SYNC_DOC) if os.path.exists(os.path.join(ROOT, SYNC_DOC)) else ""
    code = 0

    results = checks(core, base, doc) + hash_block_checks(luau, core, doc)
    failed = [(name, extra) for name, ok, extra in results if not ok]
    for name, extra in failed:
        print("FAIL: " + name + (" -- " + str(extra) if extra is not None else ""))
    print("CLAIMLOAD markers, the block against %s and the Studio sync doc: %d passed, %d failed" % (BASE, len(results) - len(failed), len(failed)))
    if failed:
        code = 1

    if base is None:
        print("FAIL: the mutation runs need TycoonCore.lua at %s (git show)" % BASE)
        return 1
    core_text = core.decode("utf-8")
    caught, lines = run_mutants(core_text, base, doc)
    for line in lines:
        if line.startswith("NOT CAUGHT"):
            print(line)
    print("CLAIMLOAD mutations: %d of %d caught, each by its named check" % (caught, len(MUTANTS)))
    if caught != len(MUTANTS):
        code = 1

    self_caught, self_lines = run_mutants(core_text, base, doc, [HARNESS_SELF_TEST])
    self_ok = self_caught == 0 and "it crashed" in self_lines[0]
    print("Harness self-test (a mutant that crashes the checks never counts): %d of 1 reported as not caught" % (1 if self_ok else 0))
    if not self_ok:
        print("FAIL: the mutation harness counted a mutant that crashed the checks as caught")
        code = 1

    runtime = runtime_checks(luau, runtime_sources())
    rfail = [(n, e) for n, ok, e in runtime if not ok]
    for name, extra in rfail:
        print("FAIL: " + name + (" -- " + str(extra) if extra is not None else ""))
    print("The claim (PR L3), the whole TycoonCore in a fake Roblox: %d passed, %d failed" % (len(runtime) - len(rfail), len(rfail)))
    if rfail:
        code = 1
    l3_caught, l3_lines = run_l3_mutants(luau)
    for line in l3_lines:
        if line.startswith("NOT CAUGHT"):
            print(line)
    print("Claim mutations (PR L3): %d of %d caught, each by its named check (never by a crash)" % (l3_caught, len(L3_MUTANTS)))
    if l3_caught != len(L3_MUTANTS):
        code = 1
    rs_caught, rs_lines = run_l3_mutants(luau, [RUNTIME_SELF_TEST])
    rs_ok = rs_caught == 0 and "crashed" in rs_lines[0]
    print("Runtime harness self-test (a mutant that crashes the test program never counts): %d of 1 reported as not caught" % (1 if rs_ok else 0))
    if not rs_ok:
        print("FAIL: the runtime mutation harness counted a crashed run as caught (%s)" % rs_lines[0])
        code = 1
    client = client_checks(luau)
    cfail = [(n, e) for n, ok, e in client if not ok]
    for name, extra in cfail:
        print("FAIL: " + name + (" -- " + str(extra) if extra is not None else ""))
    print("LobbyClient (PR L3) in a fake client: %d passed, %d failed" % (len(client) - len(cfail), len(cfail)))
    if cfail:
        code = 1
    c_caught = 0
    source = read("LobbyClient.lua")
    for label, old, new, want in CLIENT_MUTANTS:
        ok, why = client_mutant_caught(luau, source, old, new, want)
        if ok:
            c_caught += 1
        else:
            print("NOT CAUGHT: %s -- %s" % (label, why))
    print("LobbyClient mutations: %d of %d caught, each by its named check (never by an error)" % (c_caught, len(CLIENT_MUTANTS)))
    if c_caught != len(CLIENT_MUTANTS):
        code = 1
    label, old, new, want = CLIENT_SELF_TEST
    self_hit, self_why = client_mutant_caught(luau, source, old, new, want)
    self_ok = not self_hit and self_why is not None and "errored" in self_why
    print("Client harness self-test (a client that errors never counts): %d of 1 reported as not caught" % (1 if self_ok else 0))
    if not self_ok:
        print("FAIL: the client mutation harness counted a client that errored as caught (%s)" % self_why)
        code = 1
    total_checks = len(results) - len(failed) + len(runtime) - len(rfail) + len(client) - len(cfail)
    print("lobby_test.py: %d checks passed, %d of %d mutation runs caught" % (total_checks, caught + l3_caught + c_caught,
                                                                              len(MUTANTS) + len(L3_MUTANTS) + len(CLIENT_MUTANTS)))
    return code


if __name__ == "__main__":
    sys.exit(main())
