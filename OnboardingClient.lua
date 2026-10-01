-- OnboardingClient: the glowing arrow for new players (milestone 5).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds everything by itself.
-- It only shows what OnboardingServer puts on the player (attributes). It never decides or
-- grants anything, and it has nothing to type in.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local OnboardingConfig = require(ReplicatedStorage:WaitForChild("OnboardingConfig"))

local player = Players.LocalPlayer

-- The glowing arrow -------------------------------------------------------
-- A beam from the player to the target, and a bouncing arrow above the target. Both exist only
-- on this screen (made by a LocalScript), so other players never see them.

local ARROW = OnboardingConfig.Arrow

local arrowFolder = Instance.new("Folder")
arrowFolder.Name = "OnboardingArrow"
arrowFolder.Parent = workspace

local anchor = Instance.new("Part")
anchor.Name = "ArrowTarget"
anchor.Size = Vector3.new(0.2, 0.2, 0.2)
anchor.Transparency = 1
anchor.Anchored = true
anchor.CanCollide = false
anchor.CanTouch = false
anchor.CanQuery = false
anchor.Parent = arrowFolder
local targetAttachment = Instance.new("Attachment")
targetAttachment.Parent = anchor

local marker = Instance.new("BillboardGui")
marker.Name = "ArrowMarker"
marker.Size = UDim2.fromScale(4, 4) -- in studs, so it looks the same size as the world around it
marker.AlwaysOnTop = true -- seen through walls and furniture
marker.Enabled = false
marker.Parent = anchor
local markerLabel = Instance.new("TextLabel")
markerLabel.Size = UDim2.fromScale(1, 1)
markerLabel.BackgroundTransparency = 1
markerLabel.Font = Enum.Font.GothamBlack
markerLabel.Text = "▼"
markerLabel.TextScaled = true
markerLabel.TextColor3 = ARROW.color
markerLabel.TextStrokeTransparency = 0
markerLabel.Parent = marker

local beam = Instance.new("Beam")
beam.Attachment1 = targetAttachment
beam.Color = ColorSequence.new(ARROW.color)
beam.LightEmission = 1 -- glows
beam.FaceCamera = true
beam.Width0 = ARROW.beamWidth
beam.Width1 = ARROW.beamWidth
beam.Segments = 1
beam.Enabled = false
beam.Parent = arrowFolder

-- The beam starts at the player's character (a new attachment for every respawn)
local function onCharacter(character)
	local root = character:WaitForChild("HumanoidRootPart", 10)
	if not root then return end
	local attachment = Instance.new("Attachment")
	attachment.Name = "OnboardingArrowStart"
	attachment.Position = Vector3.new(0, -1.5, 0) -- about knee height
	attachment.Parent = root
	beam.Attachment0 = attachment
end
player.CharacterAdded:Connect(onCharacter)
if player.Character then
	task.spawn(onCharacter, player.Character)
end

local function refreshArrow()
	local target = player:GetAttribute("OnboardingTarget")
	local on = typeof(target) == "Vector3"
	if on then
		anchor.Position = target + Vector3.new(0, 1, 0)
	end
	beam.Enabled = on
	marker.Enabled = on
end
player:GetAttributeChangedSignal("OnboardingTarget"):Connect(refreshArrow)
refreshArrow()

-- Bounce the arrow and pulse the beam while they're showing
RunService.RenderStepped:Connect(function()
	if not marker.Enabled then return end
	local t = os.clock()
	marker.StudsOffset = Vector3.new(0, ARROW.markerHeight + math.sin(t * 5) * 0.6, 0)
	beam.Transparency = NumberSequence.new(0.25 + 0.2 * math.sin(t * 4))
end)
