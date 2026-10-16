# Kit models: the 3D models of the buildings and the furniture

Added 2026-10-16. The source files are in `assets/kit/` (made with Claude Design's "3D object" template, exported as `.glb`). In Studio they live in **ReplicatedStorage > KitModels**, one Model per key, already imported and organized by the owner (`KIT DONE: 36 moved now, 36 in KitModels, missing: none`, 2026-10-16). Nothing in the game uses them yet.

## Facts measured in Studio (2026-10-16)

- Studio's importer (**Home > Import**, "Studio Default" preset, Upload to Roblox on) reads `.glb` shapes and sizes exactly (1 unit = 1 stud) but **drops every color**: each part arrives Medium Stone Grey (163, 162, 165), Plastic, no TextureID, no SurfaceAppearance.
- It splits each object into **one MeshPart per material**. Parts are named after the material plus a number Roblox adds (`main2`, `trim11`), so the role is the name without trailing digits.
- Colors therefore come from code. The organize command below sets them from the table, and the game may recolor any role (the structure kit is meant to be restyled per building: brick garage, white office, blue glass tower, marble headquarters).
- The meshes are uploaded to Roblox under the owner's account (creator "IO E PACA"), so the Models work in the published game.

## How each Model in KitModels looks

- `KitModels.<Key>`: a Model with only MeshParts, each named by its role (`main`, `trim`, `accent`, `glass`, `dark`), with the attribute `Role`, `Anchored = true`, the colors of the table, glass parts at `Transparency` 0.3.
- `WorldPivot` is the center of the bottom face of the bounding box. Attribute `KitSize` (Vector3, X width, Y height, Z depth) is the bounding box.
- In the file the front faces +Z: the outside of a wall piece, the seat side of a chair, the screen side of a monitor, the low step of the stairs. **Unverified:** which world direction that is after import (Roblox's own "front" is -Z). Code that places a model must pin it with a Studio check, for example the `Computer` screen or the `Chair` seat facing the expected way.
- Collision: the meshes keep the importer's default collision. Code should not rely on it: pieces with holes (`WallDoor`, `WallGarage`, `WallWindow`) need invisible Part boxes for solid walls.
- Pieces the game may stretch along X (and Z for `Floor`) by resizing their parts: `Wall`, `Floor`, `RoofEdge`. They are plain along those axes.

## The 36 models

Sizes are W x D x H in studs (X x Z x Y), measured from the files and again in Studio (identical).

| Key | File | Size W x D x H | Triangles | Parts (role = color) |
|---|---|---|---|---|
| `Wall` | Structure.glb | 16 x 2 x 14 | 28 | main #C8CCD2, trim #F4F4F1 |
| `WallDoor` | Structure.glb | 16 x 2 x 14 | 56 | main #C8CCD2, trim #F4F4F1 |
| `DoorLeaf` | Structure.glb | 6 x 0.5 x 10 | 68 | trim #F4F4F1, glass #A6D6F0, dark #34373D |
| `WallWindow` | Structure.glb | 16 x 2 x 14 | 140 | main #C8CCD2, trim #F4F4F1, glass #A6D6F0 |
| `WallGlass` | Structure.glb | 16 x 2 x 14 | 140 | trim #F4F4F1, glass #A6D6F0 |
| `WallGarage` | Structure.glb | 24 x 2 x 14 | 56 | main #C8CCD2, trim #F4F4F1 |
| `GarageDoor` | Structure.glb | 20 x 1 x 12 | 108 | accent #F28A2E, dark #34373D |
| `Corner` | Structure.glb | 2 x 2 x 14 | 28 | trim #F4F4F1 |
| `Floor` | Structure.glb | 16 x 16 x 1 | 12 | main #C8CCD2 |
| `RoofEdge` | Structure.glb | 16 x 2 x 3 | 28 | trim #F4F4F1 |
| `Stairs` | Structure.glb | 8 x 16 x 15 | 156 | main #C8CCD2, trim #F4F4F1 |
| `Column` | Structure.glb | 3 x 3 x 14 | 68 | main #C8CCD2, accent #F28A2E |
| `WallElevator` | Structure.glb | 16 x 2 x 14 | 228 | main #C8CCD2, trim #F4F4F1, accent #F28A2E, dark #34373D |
| `RevolvingDoor` | Structure.glb | 10 x 10 x 12 | 260 | trim #F4F4F1, glass #A6D6F0, dark #34373D |
| `RoofCrown` | Structure.glb | 24 x 24 x 6 | 220 | main #E94B4B, accent #F2C230, dark #34373D |
| `Computer` | FurnitureA.glb | 3 x 2 x 3 | 376 | main #F4F5F7, trim #3E9BE0, dark #2F3440 |
| `Laptop` | FurnitureA.glb | 2 x 2 x 1 | 92 | main #D5DAE1, dark #2F3440 |
| `Phone` | FurnitureA.glb | 2 x 2 x 1 | 188 | main #F2803A, trim #FFFFFF, dark #2F3440 |
| `Crate` | FurnitureA.glb | 4 x 4 x 4 | 384 | main #F2A94E, trim #C77B30 |
| `BareBulb` | FurnitureA.glb | 1 x 1 x 3 | 192 | trim #D5DAE1, glass #FFE27A, dark #2F3440 |
| `Shelf` | FurnitureA.glb | 8 x 2 x 8 | 424 | main #F2A94E, trim #5DBB63, accent #3E9BE0, dark #2F3440 |
| `Plant` | FurnitureA.glb | 3 x 3 x 5 | 520 | main #5DBB63, trim #F2803A, dark #6B4A2F |
| `Workbench` | FurnitureA.glb | 8 x 4 x 4 | 348 | main #F2A94E, trim #3E9BE0, accent #F2803A, dark #2F3440 |
| `Whiteboard` | FurnitureA.glb | 8 x 2 x 7 | 312 | main #FFFFFF, trim #D5DAE1, accent #3E9BE0, dark #2F3440 |
| `CoffeeMachine` | FurnitureB.glb | 3 x 2 x 3 | 186 | dark #2F3440, main #3E9BE0, trim #C9CED6, accent #F6F4EF |
| `MeetingTable` | FurnitureB.glb | 16 x 6 x 3 | 118 | main #F2A94E, dark #2F3440, trim #C9CED6 |
| `Sofa` | FurnitureB.glb | 8 x 4 x 4 | 480 | trim #F2A94E, main #3E9BE0, accent #F2C230 |
| `Armchair` | FurnitureB.glb | 4 x 4 x 4 | 348 | trim #F2A94E, main #3E9BE0, accent #F2C230 |
| `ReceptionDesk` | FurnitureB.glb | 14 x 4 x 4 | 176 | dark #2F3440, main #F6F4EF, trim #F2A94E, accent #3E9BE0 |
| `ServerRack` | FurnitureB.glb | 3 x 4 x 8 | 364 | main #2F3440, trim #C9CED6, accent #5DBB4A |
| `BoardTable` | FurnitureB.glb | 20 x 8 x 3 | 166 | trim #F2C230, main #6E4325, dark #2F3440 |
| `Rug` | FurnitureB.glb | 12 x 8 x 0.2 | 44 | trim #F6F4EF, main #3E9BE0 |
| `LobbyTree` | FurnitureB.glb | 4 x 4 x 8 | 504 | main #F6F4EF, dark #2F3440, trim #F2A94E, accent #5DBB4A |
| `Bell` | FurnitureB.glb | 6 x 6 x 7 | 340 | dark #2F3440, main #6E4325, accent #F2C230 |
| `Chair` | Chair.glb | 3 x 3 x 4 | 508 | main #3E9BE0, trim #D5DAE1, dark #2F3440 |
| `Desk` | office_desk.glb | 8 x 4 x 3 | 144 | main #F2A94E, trim #3E9BE0, dark #2F3440 |

Groups: **structure** (one kit for all five buildings) = `Wall` to `RoofCrown`; **garage and office furniture** = `Desk`, `Chair`, `Computer`, `Laptop`, `Phone`, `Crate`, `BareBulb`, `Shelf`, `Plant`, `Workbench`, `Whiteboard`; **big office and corporate furniture** = `CoffeeMachine`, `MeetingTable`, `Sofa`, `Armchair`, `ReceptionDesk`, `ServerRack`, `BoardTable`, `Rug`, `LobbyTree`, `Bell`.

Openings in the structure pieces (from the files): `WallDoor` a hole 6 wide x 10 high, centered, from the floor; `WallGarage` a hole 20 x 12, centered, from the floor; `WallWindow` two holes 5 x 5 with bottoms at height 5; `DoorLeaf` fits the `WallDoor` hole; `GarageDoor` fits the `WallGarage` hole; `Stairs` rises 15 (a 14-high wall plus a 1-thick floor) in 15 steps, lowest step at the front.

## Re-importing (if KitModels is ever lost)

1. Studio, **Home > Import**, select the five files in `assets/kit/`, keep the default settings, Import.
2. Paste the command below in the command bar, run it with Cmd+Enter. It moves every known model into `ReplicatedStorage.KitModels`, colors it, and deletes the emptied import scenes from Workspace. It skips keys already in KitModels, so it can run twice.
3. The last Output line must say `missing: none`. Then **File > Save to Roblox** (never Publish).

```lua
local P={Wall={main="C8CCD2",trim="F4F4F1"},WallDoor={main="C8CCD2",trim="F4F4F1"},DoorLeaf={trim="F4F4F1",glass="A6D6F0",dark="34373D"},WallWindow={main="C8CCD2",trim="F4F4F1",glass="A6D6F0"},WallGlass={trim="F4F4F1",glass="A6D6F0"},WallGarage={main="C8CCD2",trim="F4F4F1"},GarageDoor={accent="F28A2E",dark="34373D"},Corner={trim="F4F4F1"},Floor={main="C8CCD2"},RoofEdge={trim="F4F4F1"},Stairs={main="C8CCD2",trim="F4F4F1"},Column={main="C8CCD2",accent="F28A2E"},WallElevator={main="C8CCD2",trim="F4F4F1",accent="F28A2E",dark="34373D"},RevolvingDoor={trim="F4F4F1",glass="A6D6F0",dark="34373D"},RoofCrown={main="E94B4B",accent="F2C230",dark="34373D"},Computer={main="F4F5F7",trim="3E9BE0",dark="2F3440"},Laptop={main="D5DAE1",dark="2F3440"},Phone={main="F2803A",trim="FFFFFF",dark="2F3440"},Crate={main="F2A94E",trim="C77B30"},BareBulb={trim="D5DAE1",glass="FFE27A",dark="2F3440"},Shelf={main="F2A94E",trim="5DBB63",accent="3E9BE0",dark="2F3440"},Plant={main="5DBB63",trim="F2803A",dark="6B4A2F"},Workbench={main="F2A94E",trim="3E9BE0",accent="F2803A",dark="2F3440"},Whiteboard={main="FFFFFF",trim="D5DAE1",accent="3E9BE0",dark="2F3440"},CoffeeMachine={dark="2F3440",main="3E9BE0",trim="C9CED6",accent="F6F4EF"},MeetingTable={main="F2A94E",dark="2F3440",trim="C9CED6"},Sofa={trim="F2A94E",main="3E9BE0",accent="F2C230"},Armchair={trim="F2A94E",main="3E9BE0",accent="F2C230"},ReceptionDesk={dark="2F3440",main="F6F4EF",trim="F2A94E",accent="3E9BE0"},ServerRack={main="2F3440",trim="C9CED6",accent="5DBB4A"},BoardTable={trim="F2C230",main="6E4325",dark="2F3440"},Rug={trim="F6F4EF",main="3E9BE0"},LobbyTree={main="F6F4EF",dark="2F3440",trim="F2A94E",accent="5DBB4A"},Bell={dark="2F3440",main="6E4325",accent="F2C230"},Chair={main="3E9BE0",trim="D5DAE1",dark="2F3440"},Desk={main="F2A94E",trim="3E9BE0",dark="2F3440"}}
local RS = game:GetService("ReplicatedStorage")
local kit = RS:FindFirstChild("KitModels") or Instance.new("Folder")
kit.Name = "KitModels"; kit.Parent = RS
local deskRole = {office_desk = "main", office_desk2 = "trim", office_desk3 = "dark"}
local roots = {}
for _, c in ipairs(workspace:GetChildren()) do if c.Name == "AuxScene" then table.insert(roots, c) end end
local moved = 0
for _, root in ipairs(roots) do
	for _, m in ipairs(root:GetDescendants()) do
		local key = (m.Name == "office_desk_Node") and "Desk" or m.Name
		if m:IsA("Model") and P[key] then
			if kit:FindFirstChild(key) then
				warn("SKIP " .. key .. ": already in KitModels")
			else
				local out = Instance.new("Model"); out.Name = key
				out.WorldPivot = CFrame.new(m:GetPivot().Position)
				for _, p in ipairs(m:GetDescendants()) do
					if p:IsA("MeshPart") then
						local role = (key == "Desk") and deskRole[p.Name] or (p.Name:gsub("%d+$", ""))
						local hex = role and P[key][role]
						if hex then
							p.Name = role; p.Color = Color3.fromHex(hex); p.Anchored = true
							p:SetAttribute("Role", role)
							if role == "glass" then p.Transparency = 0.3 end
							p.Parent = out
						else
							warn("NO COLOR " .. key .. " " .. p.Name)
						end
					end
				end
				local cf, size = out:GetBoundingBox()
				out.WorldPivot = CFrame.new(cf.Position.X, cf.Position.Y - size.Y / 2, cf.Position.Z)
				out:SetAttribute("KitSize", size)
				out.Parent = kit
				moved += 1
				print(("OK %s %.2f x %.2f x %.2f"):format(key, size.X, size.Z, size.Y))
			end
		end
	end
	local left = 0
	for _, d in ipairs(root:GetDescendants()) do if d:IsA("BasePart") then left += 1 end end
	if left == 0 then root:Destroy() else warn("KEPT a scene in Workspace: " .. left .. " parts not recognised") end
end
local missing = {}
for k in pairs(P) do if not kit:FindFirstChild(k) then table.insert(missing, k) end end
print(("KIT DONE: %d moved now, %d in KitModels, missing: %s"):format(moved, #kit:GetChildren(), #missing == 0 and "none" or table.concat(missing, ", ")))

```
