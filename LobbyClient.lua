-- LobbyClient: the plaza's banner and the arrow to the nearest free garage (lobby L3).
-- WHERE: a LocalScript named exactly LobbyClient in StarterPlayer > StarterPlayerScripts.
--
-- Client only, display only. While LobbyConfig.ClaimEnabled is on and this player has no garage yet (the server's
-- attribute Garage = 0), it shows a banner ("Walk to a free garage to start your company") and a marker over the
-- claim post of the nearest garage whose State is Free. It never fires a remote and never names a garage to the server:
-- claiming is the server's prompt on the post. With the claim off it shows nothing.
-- Once this player has a garage (Garage ~= 0), the other garages' FREE signs, green lamps and "Claim garage" prompts are
-- hidden on this client only (overhaul phase 1, the owner's point 6): a property set here never reaches the server or
-- another player, and the server still refuses every claim from a player who has a garage. A player still on the plaza
-- sees them exactly as the server sets them (State Free: shown; MovingIn or Closing: the sign only; Taken: nothing).
-- The welcome card (overhaul phase 4): the one time a session starts on the plaza, a card under the banner tells the
-- story in four lines (a founder, a garage, hires, funding rounds, the IPO) with a "Got it" button; it goes with the
-- button or with the claim, and never comes back in the session. Display only, LobbyConfig.Texts.Welcome.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local LobbyConfig = require(ReplicatedStorage:WaitForChild("LobbyConfig"))

local player = Players.LocalPlayer
local CHECK_SECONDS = 0.5 -- how often the nearest free garage is looked for again

if not LobbyConfig.ClaimEnabled then
	return -- the claim is off: every player gets a garage at once, nothing to show
end

local function make(class, props)
	local inst = Instance.new(class)
	for k, v in pairs(props) do
		if k ~= "Parent" then
			inst[k] = v
		end
	end
	inst.Parent = props.Parent
	return inst
end

local gui = make("ScreenGui", {
	Name = "LobbyGui",
	ResetOnSpawn = false,
	DisplayOrder = -1, -- with the HUD, under every window
	Enabled = false,
	Parent = player:WaitForChild("PlayerGui"),
})

local banner = make("TextLabel", {
	Name = "Banner",
	BackgroundColor3 = Color3.fromRGB(28, 30, 38),
	BackgroundTransparency = 0.15,
	TextColor3 = Color3.fromRGB(255, 255, 255),
	Font = Enum.Font.GothamBold,
	TextScaled = true,
	Text = LobbyConfig.Texts.Banner,
	Parent = gui,
})
make("UICorner", { CornerRadius = UDim.new(0, 10), Parent = banner })
make("UIPadding", { PaddingLeft = UDim.new(0, 10), PaddingRight = UDim.new(0, 10), PaddingTop = UDim.new(0, 4), PaddingBottom = UDim.new(0, 4), Parent = banner })

-- The welcome card: the story, once per session, while the player is on the plaza
local WELCOME_WIDTH, WELCOME_HEIGHT = 300, 150
local welcome = make("Frame", {
	Name = "Welcome",
	BackgroundColor3 = Color3.fromRGB(28, 30, 38),
	BackgroundTransparency = 0.1,
	Visible = LobbyConfig.Texts.Welcome ~= nil,
	Parent = gui,
})
make("UICorner", { CornerRadius = UDim.new(0, 12), Parent = welcome })
make("UIStroke", { Thickness = 2, Color = Color3.fromRGB(255, 200, 60), Transparency = 0.4, Parent = welcome })
local welcomeTitle = make("TextLabel", {
	Name = "Title",
	Position = UDim2.fromOffset(12, 8),
	Size = UDim2.new(1, -24, 0, 24),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	TextScaled = true,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextColor3 = Color3.fromRGB(255, 200, 60),
	Text = LobbyConfig.Texts.WelcomeTitle or "",
	Parent = welcome,
})
make("UITextSizeConstraint", { MaxTextSize = 20, MinTextSize = 10, Parent = welcomeTitle })
local welcomeBody = make("TextLabel", {
	Name = "Body",
	Position = UDim2.fromOffset(12, 36),
	Size = UDim2.new(1, -24, 0, 70),
	BackgroundTransparency = 1,
	Font = Enum.Font.Gotham,
	TextScaled = true,
	TextWrapped = true,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	TextColor3 = Color3.fromRGB(255, 255, 255),
	Text = LobbyConfig.Texts.Welcome or "",
	Parent = welcome,
})
make("UITextSizeConstraint", { MaxTextSize = 15, MinTextSize = 9, Parent = welcomeBody })
local welcomeButton = make("TextButton", {
	Name = "GotIt",
	AnchorPoint = Vector2.new(1, 1),
	Position = UDim2.new(1, -12, 1, -10),
	Size = UDim2.fromOffset(110, 30),
	BackgroundColor3 = Color3.fromRGB(0, 200, 90),
	Font = Enum.Font.GothamBold,
	TextScaled = true,
	TextColor3 = Color3.fromRGB(255, 255, 255),
	Text = LobbyConfig.Texts.WelcomeButton or "OK",
	Parent = welcome,
})
make("UICorner", { CornerRadius = UDim.new(0, 8), Parent = welcomeButton })
make("UITextSizeConstraint", { MaxTextSize = 16, MinTextSize = 10, Parent = welcomeButton })
welcomeButton.Activated:Connect(function()
	welcome.Visible = false
end)

-- Under the HUD and the valuation bar (IpoClient placeHud): right of the button column on tall screens, under the
-- button row (and the bar, when it wraps under it) on short ones
local function placeBanner()
	local size = gui.AbsoluteSize
	if size.Y < 460 then
		local rowEnd = 10 + 5 * 72
		local wrapped = size.X - rowEnd - 10 < 180 + 70 -- the bar goes under the row (IpoClient: width under 180, chip room 70)
		banner.Position = UDim2.fromOffset(10, wrapped and 146 or 76)
		banner.Size = UDim2.fromOffset(math.min(size.X - 20, 360), 34)
	else
		banner.Position = UDim2.fromOffset(98, 84)
		banner.Size = UDim2.fromOffset(math.max(0, math.min(size.X - 108, 320)), 34)
	end
	-- the welcome card under the banner, as wide, never over the thumbstick's zone (the bottom 180)
	local x, y = banner.Position.X.Offset, banner.Position.Y.Offset + 34 + 8
	local width = math.max(160, math.min(WELCOME_WIDTH, banner.Size.X.Offset))
	welcome.Position = UDim2.fromOffset(x, y)
	welcome.Size = UDim2.fromOffset(width, math.min(WELCOME_HEIGHT, math.max(100, size.Y - y - 180)))
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(placeBanner)
placeBanner()

-- The marker over the nearest free garage's claim post (this client only). A BillboardGui goes straight in PlayerGui
-- (inside a ScreenGui it would not show in the world); it is hidden on its own when the banner hides.
local marker = make("BillboardGui", {
	Name = "FreeGarageMarker",
	Size = UDim2.fromOffset(120, 60),
	StudsOffset = Vector3.new(0, 7, 0),
	AlwaysOnTop = false, -- overhaul 2 phase 5 (the owner's point 4): hidden by walls like the world, never drawn on top
	ResetOnSpawn = false,
	Enabled = false,
	Parent = player:WaitForChild("PlayerGui"),
})
make("TextLabel", {
	Size = UDim2.fromScale(1, 1),
	BackgroundTransparency = 1,
	TextColor3 = Color3.fromRGB(90, 230, 120),
	TextStrokeTransparency = 0,
	Font = Enum.Font.GothamBold,
	TextScaled = true,
	Text = "▼ " .. LobbyConfig.Texts.Free,
	Parent = marker,
})

local function onPlaza()
	return player:GetAttribute("Garage") == 0
end

-- The claim post of the nearest garage that is Free, or nil. Each post stands in its garage's ClaimSpot, a Persistent
-- model, so it is here even with streaming on and the garage far away.
local function nearestFreePost()
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	local garages = workspace:FindFirstChild("Garages")
	if not (root and garages) then return nil end
	local best, bestDistance = nil, math.huge
	for _, garage in ipairs(garages:GetChildren()) do
		local spot = garage:FindFirstChild("ClaimSpot")
		local post = spot and spot:FindFirstChild("ClaimPost")
		if post and garage:GetAttribute("State") == "Free" then
			local d = (post.Position - root.Position).Magnitude
			if d < bestDistance then
				best, bestDistance = post, d
			end
		end
	end
	return best
end

-- The claim spots as this client sees them: with a garage, every FREE sign (the board on the post), lamp and prompt is hidden here; without one,
-- what the server set (the same rule as TycoonCore's setGarageState, from the garage's State attribute)
local function showClaimSpots(show)
	local garages = workspace:FindFirstChild("Garages")
	if not garages then return end
	for _, garage in ipairs(garages:GetChildren()) do
		local spot = garage:FindFirstChild("ClaimSpot")
		local post = spot ~= nil and spot:FindFirstChild("ClaimPost") or nil
		if post then
			local state = garage:GetAttribute("State")
			local free = show and state == "Free"
			for _, child in ipairs(post:GetChildren()) do
				if child.ClassName == "ProximityPrompt" then
					child.Enabled = free
				elseif child.ClassName == "BillboardGui" then
					child.Enabled = show and state ~= "Taken"
				end
			end
			local lamp = spot:FindFirstChild("FreeLamp")
			if lamp then
				lamp.Transparency = free and 0 or 1
			end
			local board = spot:FindFirstChild("FreeSign") -- overhaul 2 phase 5: the board on the post (its SurfaceGuis)
			if board then
				local shown = show and state ~= "Taken"
				board.Transparency = shown and 0 or 1
				for _, child in ipairs(board:GetChildren()) do
					if child.ClassName == "SurfaceGui" then
						child.Enabled = shown
					end
				end
			end
		end
	end
end

local function refresh()
	local show = onPlaza()
	gui.Enabled = show
	local post = show and nearestFreePost() or nil
	marker.Adornee = post
	marker.Enabled = post ~= nil
	showClaimSpots(show)
end

player:GetAttributeChangedSignal("Garage"):Connect(refresh)
local waited = 0
RunService.Heartbeat:Connect(function(dt)
	waited += dt
	if waited >= CHECK_SECONDS then
		waited = 0
		refresh()
	end
end)
refresh()
