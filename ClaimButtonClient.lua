-- ClaimButtonClient: a big "Claim garage" button on phones, next to the server's claim prompt (ux lane).
-- WHERE: a LocalScript named exactly ClaimButtonClient in StarterPlayer > StarterPlayerScripts. It builds its screen itself.
--
-- Client only, display only. Each garage's claim post has the server's ProximityPrompt "Claim garage" (TycoonCore
-- buildGarages; on only while the garage is Free and LobbyConfig.ClaimEnabled is on). On a phone that prompt is a
-- small button floating in the world. While Roblox shows one of those prompts for touch input, and this player has no
-- garage yet (the server's attribute Garage = 0), this script shows one big button at the bottom of the screen.
-- Tapping it presses THAT prompt (InputHoldBegin, then InputHoldEnd after the prompt's own hold time), exactly as a tap
-- on the prompt would: the server's Triggered handler checks everything as before (the distance, the rate, the
-- garage's state, the switch) and tells the player why when it refuses. It never fires a remote, never names a garage
-- and never decides anything. With the claim off it shows nothing; while a window is open (PlayerGui attribute
-- "OpenPanel") it hides, like the task tray.
--
-- Where the button goes (px from the GUI's top-left; GUI = the screen minus Roblox's top bar). It stays clear of
-- Roblox's touch controls (thumbstick x < 170 and y > H-170; jump button x > W-150 and y > H-130, as in TaskClient)
-- and of the Shop's pop-up lane (bottom -16, 48 high), which shows the server's "why not" messages:
--   short screens (height under 460, the HUD's switch): in the gap between the thumbstick and the jump button, as wide
--     as the gap allows (at most 260), bottom at H-72 (just above the -16 lane). 667x375: x 213-473, y 243-303;
--     568x320: x 178-410, y 188-248.
--   tall screens: centered, at most 260 wide (16 px side margins), bottom at H-176 (above the thumbstick).
--     320x568: x 30-290, y 332-392. The -184 and -240 lanes (Onboarding, Daily) start only after the claim, when this
--     button is gone.
-- The button is 60 high (a touch target is at least 44).
--
-- Two claim prompts can show at once (two free garages side by side). The script keeps every claim prompt Roblox shows
-- for touch, and the button names and presses the nearest one to the player (the newest shown when there is no
-- character yet, or two are as near). It looks again twice a second while two or more show, so walking along the row
-- moves the button to the next garage. One of them hiding never hides the button while another is still shown.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ProximityPromptService = game:GetService("ProximityPromptService")

local LobbyConfig = require(ReplicatedStorage:WaitForChild("LobbyConfig"))

if not LobbyConfig.ClaimEnabled then
	return -- the claim is off: every player gets a garage at once, there is no prompt
end

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local PRESSING_TEXT = "Claiming..."

local COLORS = {
	text = Color3.new(1, 1, 1),
	buy = Color3.fromRGB(0, 200, 90), -- the green of every buy button
	busy = Color3.fromRGB(70, 74, 86),
}

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

-- Text shrinks to fit small phone screens but never grows past maxSize
local function fitText(inst, maxSize)
	inst.TextScaled = true
	make("UITextSizeConstraint", { MaxTextSize = maxSize, MinTextSize = 8, Parent = inst })
end

-- CLAIMBUTTON-START
-- (tools/hud_test.py runs the code between the CLAIMBUTTON markers, so keep it free of Roblox calls.)
-- A GUI of w x h pixels -> the button's rectangle { x, y, w, h }.
local BUTTON_HEIGHT = 60
local BUTTON_MAX_WIDTH = 260
local THUMBSTICK_RIGHT = 170 -- the thumbstick's zone ends here (x)
local JUMP_LEFT_FROM_RIGHT = 150 -- the jump button's zone starts at W minus this (x)
local SHORT_BOTTOM = 72 -- short screens: the button's bottom is this far above the GUI's bottom
local TALL_BOTTOM = 176 -- tall screens: the same, above the thumbstick's zone (170)
local SIDE_MARGIN = 16
local RECHECK = 0.5 -- seconds between looks for the nearest prompt, only while two or more show
-- The distance between two points ({ X, Y, Z }: a Vector3 or a plain table)
local function distance(a, b)
	local dx, dy, dz = a.X - b.X, a.Y - b.Y, a.Z - b.Z
	return math.sqrt(dx * dx + dy * dy + dz * dz)
end
-- shown = { [key] = { pos = point or nil, order = number } } -> the key nearest to from (nil: no character), ties and
-- unknown places going to the highest order (the newest shown); nil when shown is empty
local function nearestKey(shown, from)
	local bestKey, bestDist, bestOrder = nil, math.huge, -math.huge
	for key, entry in pairs(shown) do
		local d = (from and entry.pos) and distance(from, entry.pos) or math.huge
		if d < bestDist or (d == bestDist and entry.order > bestOrder) then
			bestKey, bestDist, bestOrder = key, d, entry.order
		end
	end
	return bestKey
end
local function buttonLayout(w, h)
	local left, right, bottom
	if h < 460 then
		left, right, bottom = THUMBSTICK_RIGHT + 8, w - JUMP_LEFT_FROM_RIGHT - 8, SHORT_BOTTOM
	else
		left, right, bottom = SIDE_MARGIN, w - SIDE_MARGIN, TALL_BOTTOM
	end
	local width = math.max(0, math.min(BUTTON_MAX_WIDTH, right - left))
	return { x = math.floor(left + (right - left - width) / 2), y = h - bottom - BUTTON_HEIGHT, w = width, h = BUTTON_HEIGHT }
end
-- CLAIMBUTTON-END

-- With the HUD, above the lobby banner (-1), under every window (the button hides while one is open anyway)
local gui = make("ScreenGui", {
	Name = "ClaimButtonGui",
	ResetOnSpawn = false,
	DisplayOrder = 0,
	Enabled = false,
	Parent = playerGui,
})

local button = make("TextButton", {
	Name = "ClaimButton",
	BackgroundColor3 = COLORS.buy,
	AutoButtonColor = true,
	Text = "",
	Parent = gui,
})
make("UICorner", { CornerRadius = UDim.new(0, 12), Parent = button })
make("UIStroke", { Thickness = 2, Color = COLORS.text, Transparency = 0.4, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = button })
local title = make("TextLabel", {
	Name = "Title",
	Position = UDim2.new(0, 10, 0, 6),
	Size = UDim2.new(1, -20, 0, 30),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = LobbyConfig.Texts.Prompt,
	TextColor3 = COLORS.text,
	Parent = button,
})
fitText(title, 26)
local subtitle = make("TextLabel", {
	Name = "Garage",
	Position = UDim2.new(0, 10, 0, 36),
	Size = UDim2.new(1, -20, 0, 18),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.text,
	Parent = button,
})
fitText(subtitle, 16)

local function place()
	local size = gui.AbsoluteSize
	local r = buttonLayout(size.X, size.Y)
	button.Position = UDim2.fromOffset(r.x, r.y)
	button.Size = UDim2.fromOffset(r.w, r.h)
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(place)
place()

-- A claim prompt is the ProximityPrompt on a garage's ClaimPost, inside its ClaimSpot model (TycoonCore buildGarages)
local function isClaimPrompt(prompt)
	local post = prompt.Parent
	return post ~= nil and post.Name == "ClaimPost" and post.Parent ~= nil and post.Parent.Name == "ClaimSpot"
end

local shownPrompts = {} -- every claim prompt Roblox shows for touch right now: { [prompt] = order shown }
local shownCount = 0 -- how many prompts were ever shown (the order of the newest)
local pressing = nil -- the prompt a tap is holding, or nil

-- Where a claim prompt stands (its ClaimPost), or nil
local function promptPlace(prompt)
	local post = prompt.Parent
	local ok, pos = pcall(function()
		return post.Position
	end)
	return ok and pos or nil
end

-- The shown claim prompt nearest to the player, or nil. A prompt no longer on a claim post (its garage was reset) is
-- forgotten here, in case Roblox never said it hid.
local function nearestPrompt()
	local entries = {}
	for prompt, order in pairs(shownPrompts) do
		if isClaimPrompt(prompt) then
			entries[prompt] = { pos = promptPlace(prompt), order = order }
		else
			shownPrompts[prompt] = nil
		end
	end
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	return nearestKey(entries, root and root.Position or nil)
end

local function refresh()
	local prompt = pressing or nearestPrompt()
	local show = prompt ~= nil and player:GetAttribute("Garage") == 0 and playerGui:GetAttribute("OpenPanel") == nil
	gui.Enabled = show
	if prompt then
		subtitle.Text = prompt.ObjectText
	end
	button.BackgroundColor3 = pressing and COLORS.busy or COLORS.buy
	title.Text = pressing and PRESSING_TEXT or LobbyConfig.Texts.Prompt
end

-- While two or more prompts show, look again for the nearest twice a second (the player walks); one look at a time
local rechecking = false
local function recheck()
	local count = 0
	for _ in pairs(shownPrompts) do
		count += 1
	end
	if rechecking or count < 2 then return end
	rechecking = true
	task.delay(RECHECK, function()
		rechecking = false
		refresh()
		recheck()
	end)
end

ProximityPromptService.PromptShown:Connect(function(prompt, inputType)
	if inputType == Enum.ProximityPromptInputType.Touch and isClaimPrompt(prompt) then
		shownCount += 1
		shownPrompts[prompt] = shownCount
		refresh()
		recheck()
	end
end)
ProximityPromptService.PromptHidden:Connect(function(prompt)
	if shownPrompts[prompt] then
		shownPrompts[prompt] = nil
		refresh()
	end
end)

-- The tap: hold the nearest shown prompt for its own hold time (plus a little), then let go. Roblox triggers the prompt
-- and the server's handler decides; a second tap while holding does nothing.
button.Activated:Connect(function()
	local prompt = nearestPrompt()
	if pressing or not prompt or player:GetAttribute("Garage") ~= 0 then return end
	pressing = prompt
	refresh()
	prompt:InputHoldBegin()
	task.delay(prompt.HoldDuration + 0.15, function()
		pcall(function()
			prompt:InputHoldEnd()
		end)
		pressing = nil
		refresh()
	end)
end)

player:GetAttributeChangedSignal("Garage"):Connect(refresh)
playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(refresh)
refresh()
