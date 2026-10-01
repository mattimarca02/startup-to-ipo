-- OnboardingClient: the glowing arrow and the goal tracker for new players (milestone 5).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds everything by itself.
-- It only shows what OnboardingServer puts on the player (attributes). It never decides or
-- grants anything, and it has nothing to type in. Its only request is closing the tracker.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local OnboardingConfig = require(ReplicatedStorage:WaitForChild("OnboardingConfig"))
local IpoConfig = require(ReplicatedStorage:WaitForChild("IpoConfig")) -- money format for the Seed goal
local onboardingRemotes = ReplicatedStorage:WaitForChild("OnboardingRemotes")
local onboardingAction = onboardingRemotes:WaitForChild("OnboardingAction")
local onboardingNotify = onboardingRemotes:WaitForChild("OnboardingNotify")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90), -- same green as the buy pad
	gold = Color3.fromRGB(255, 200, 60),
}

-- UI helpers ------------------------------------------------------------

local function make(className, props)
	local inst = Instance.new(className)
	local parent = props.Parent
	props.Parent = nil
	for key, value in pairs(props) do
		inst[key] = value
	end
	inst.Parent = parent
	return inst
end

local function round(inst, radius)
	make("UICorner", { CornerRadius = UDim.new(0, radius), Parent = inst })
end

-- Text shrinks to fit small phone screens but never grows past maxSize
local function fitText(inst, maxSize)
	inst.TextScaled = true
	make("UITextSizeConstraint", { MaxTextSize = maxSize, MinTextSize = 8, Parent = inst })
end

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
marker.Size = UDim2.fromScale(ARROW.markerSize, ARROW.markerSize) -- in studs, so it looks the same size as the world around it
marker.AlwaysOnTop = true -- seen through walls and furniture
marker.Enabled = false
marker.Parent = anchor

-- A soft round backdrop behind the chevron, so it reads against any floor or wall color
local markerBackdrop = Instance.new("Frame")
markerBackdrop.AnchorPoint = Vector2.new(0.5, 0.5)
markerBackdrop.Position = UDim2.fromScale(0.5, 0.5)
markerBackdrop.Size = UDim2.fromScale(0.85, 0.85)
markerBackdrop.BackgroundColor3 = Color3.new(0, 0, 0)
markerBackdrop.BackgroundTransparency = 0.5
markerBackdrop.Parent = marker
local markerBackdropCorner = Instance.new("UICorner")
markerBackdropCorner.CornerRadius = UDim.new(1, 0) -- fully round
markerBackdropCorner.Parent = markerBackdrop

local markerScale = Instance.new("UIScale") -- breathes in time with the bob
markerScale.Parent = marker

local markerLabel = Instance.new("TextLabel")
markerLabel.AnchorPoint = Vector2.new(0.5, 0.5)
markerLabel.Position = UDim2.fromScale(0.5, 0.5)
markerLabel.Size = UDim2.fromScale(0.75, 0.75)
markerLabel.BackgroundTransparency = 1
markerLabel.Font = Enum.Font.GothamBlack
markerLabel.Text = "▼"
markerLabel.TextScaled = true
markerLabel.TextColor3 = ARROW.color
markerLabel.TextStrokeTransparency = 0.3
markerLabel.TextStrokeColor3 = Color3.new(0, 0, 0)
markerLabel.Parent = marker

local beam = Instance.new("Beam")
beam.Attachment1 = targetAttachment
beam.Color = ColorSequence.new(ARROW.color)
beam.LightEmission = 1 -- glows
beam.FaceCamera = true
beam.Width0 = ARROW.beamWidthNear -- tapered: thin at the player, wider at the target, reads as a direction
beam.Width1 = ARROW.beamWidthFar
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

-- Bounce the chevron, pulse its size gently, and pulse the beam while they're showing
RunService.RenderStepped:Connect(function()
	if not marker.Enabled then return end
	local t = os.clock()
	local bob = math.sin(t * ARROW.bobSpeed)
	marker.StudsOffset = Vector3.new(0, ARROW.markerHeight + bob * ARROW.bobAmplitude, 0)
	markerScale.Scale = 1 + (bob * 0.5 + 0.5) * ARROW.pulseAmount
	beam.Transparency = NumberSequence.new(0.25 + 0.2 * math.sin(t * 4))
end)

-- Goal tracker ------------------------------------------------------------
-- A small card right under the IPO valuation bar (IpoClient), the same width, so it follows the
-- HUD layout on every screen size. Hidden while a window is open ("OpenPanel").

local HEADER_HEIGHT = 30
local ROW_HEIGHT = 22
local GAP = 6 -- between the valuation bar and the card

local gui = make("ScreenGui", {
	Name = "OnboardingGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	Parent = playerGui,
})

-- Pop-up messages (e.g. the free egg): bottom middle, clear of the other windows' own toasts
local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -184),
	Size = UDim2.new(0.6, 0, 0, 48),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.1,
	Font = Enum.Font.GothamBold,
	TextColor3 = COLORS.gold,
	Visible = false,
	ZIndex = 10,
	Parent = gui,
})
round(toast, 12)
fitText(toast, 22)
make("UISizeConstraint", { MaxSize = Vector2.new(520, 48), Parent = toast })

local toastToken = 0
local function showToast(text)
	toastToken += 1
	local myToken = toastToken
	toast.Text = text
	toast.Visible = true
	task.delay(3.5, function()
		if toastToken == myToken then
			toast.Visible = false
		end
	end)
end
onboardingNotify.OnClientEvent:Connect(showToast)

local card = make("Frame", {
	Name = "GoalTracker",
	Size = UDim2.fromOffset(250, HEADER_HEIGHT + ROW_HEIGHT * #OnboardingConfig.Goals + 8),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.15,
	Visible = false,
	Parent = gui,
})
round(card, 12)
make("UIStroke", { Thickness = 2, Color = COLORS.buy, Transparency = 0.4, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = card })

local title = make("TextLabel", {
	Position = UDim2.fromOffset(10, 4),
	Size = UDim2.new(1, -50, 0, HEADER_HEIGHT - 8),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "🎯 Goals",
	TextColor3 = COLORS.buy,
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = card,
})
fitText(title, 16)

-- X: closes the tracker for good (the server saves it)
local closeButton = make("TextButton", {
	Name = "Close",
	AnchorPoint = Vector2.new(1, 0),
	Position = UDim2.new(1, -4, 0, 4),
	Size = UDim2.fromOffset(30, 26),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.3,
	Font = Enum.Font.GothamBold,
	Text = "✕",
	TextColor3 = COLORS.subtext,
	Parent = card,
})
round(closeButton, 8)
fitText(closeButton, 16)

local rows = {} -- goal key -> { name, progress }
for i, goal in ipairs(OnboardingConfig.Goals) do
	local y = HEADER_HEIGHT + (i - 1) * ROW_HEIGHT
	local name = make("TextLabel", {
		Position = UDim2.fromOffset(10, y),
		Size = UDim2.new(0.6, -10, 0, ROW_HEIGHT - 2),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = card,
	})
	fitText(name, 15)
	local progress = make("TextLabel", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -10, 0, y),
		Size = UDim2.new(0.4, -10, 0, ROW_HEIGHT - 2),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "",
		TextColor3 = COLORS.subtext,
		TextXAlignment = Enum.TextXAlignment.Right,
		Parent = card,
	})
	fitText(progress, 15)
	rows[goal.key] = { name = name, progress = progress }
end

-- Sits under the valuation bar. IpoClient places that bar with offsets in a ScreenGui like this
-- one, so the same numbers line up. Without it (IpoClient missing), a fixed spot top-left.
local valuationBar
local function place()
	if valuationBar and valuationBar.Parent then
		local position, size = valuationBar.Position, valuationBar.Size
		card.Position = UDim2.fromOffset(position.X.Offset, position.Y.Offset + size.Y.Offset + GAP)
		card.Size = UDim2.fromOffset(size.X.Offset, card.Size.Y.Offset)
	elseif gui.AbsoluteSize.Y < 460 then -- short phone screen: under the HUD button row
		card.Position = UDim2.fromOffset(10, 76)
		card.Size = UDim2.fromOffset(math.min(250, gui.AbsoluteSize.X - 20), card.Size.Y.Offset)
	else
		card.Position = UDim2.fromOffset(98, 84)
		card.Size = UDim2.fromOffset(math.clamp(gui.AbsoluteSize.X - 108, 180, 250), card.Size.Y.Offset)
	end
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(place)
place()
task.spawn(function()
	local ipoGui = playerGui:WaitForChild("IpoGui", 30) -- the bar is in IpoGui, not IpoWindowGui
	valuationBar = ipoGui and ipoGui:WaitForChild("ValuationBar", 30)
	if valuationBar then
		valuationBar:GetPropertyChangedSignal("Position"):Connect(place)
		valuationBar:GetPropertyChangedSignal("Size"):Connect(place)
		place()
	end
end)

local function progressText(goal, current, target)
	if goal.kind == "stage" then
		return IpoConfig.formatShort(current) .. " / " .. IpoConfig.formatShort(target)
	end
	return current .. "/" .. target
end

local closed = false -- closed with the X on this screen (the server saves it too)
local celebrating = false

local function refreshTracker()
	local allDone = true
	for _, goal in ipairs(OnboardingConfig.Goals) do
		local row = rows[goal.key]
		local current = player:GetAttribute("OnboardingGoal_" .. goal.key)
		local target = player:GetAttribute("OnboardingGoalTarget_" .. goal.key)
		local done = typeof(current) == "number" and typeof(target) == "number" and current >= target
		row.name.Text = (done and "✅" or goal.icon) .. " " .. goal.text
		row.name.TextColor3 = done and COLORS.subtext or COLORS.text
		row.progress.Text = typeof(current) == "number" and typeof(target) == "number" and progressText(goal, current, target) or ""
		row.progress.TextColor3 = done and COLORS.buy or COLORS.subtext
		allDone = allDone and done
	end
	local show = player:GetAttribute("OnboardingTracker") == true and not closed
	-- Every goal just got finished: show the ticks for a moment before the card goes away.
	-- Only a message: finishing the goals gives nothing.
	if not show and allDone and card.Visible and not closed and not celebrating then
		celebrating = true
		title.Text = "🎉 All goals done!"
		title.TextColor3 = COLORS.gold
		closeButton.Visible = false
		task.delay(3, function()
			celebrating = false
			closed = true
			card.Visible = false
		end)
	end
	if celebrating then return end
	card.Visible = show and playerGui:GetAttribute("OpenPanel") == nil
end

closeButton.Activated:Connect(function()
	closed = true
	card.Visible = false
	task.spawn(function()
		local ok, result, message = pcall(function()
			return onboardingAction:InvokeServer("DismissTracker")
		end)
		if not ok or not result then
			warn("Couldn't save closing the goal tracker: " .. tostring(ok and message or result))
		end
	end)
end)

player.AttributeChanged:Connect(function(name)
	if name == "OnboardingTracker" and player:GetAttribute(name) == true and not celebrating then
		-- The server shows it again (only the Studio Debug restart does that): start fresh
		closed = false
		title.Text = "🎯 Goals"
		title.TextColor3 = COLORS.buy
		closeButton.Visible = true
	end
	if name == "OnboardingTracker" or string.sub(name, 1, 14) == "OnboardingGoal" then
		refreshTracker()
	end
end)
playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(refreshTracker)
refreshTracker()
