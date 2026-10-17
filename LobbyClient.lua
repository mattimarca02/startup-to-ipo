-- LobbyClient: the plaza's banner and the arrow to the nearest free garage (lobby L3).
-- WHERE: a LocalScript named exactly LobbyClient in StarterPlayer > StarterPlayerScripts.
--
-- Client only, display only. While LobbyConfig.ClaimEnabled is on and this player has no garage yet (the server's
-- attribute Garage = 0), it shows a banner ("Walk to a free garage to start your company") and a marker over the
-- claim post of the nearest garage whose State is Free. It never fires a remote and never names a garage to the server:
-- claiming is the server's prompt on the post. With the claim off it shows nothing.

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
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(placeBanner)
placeBanner()

-- The marker over the nearest free garage's claim post (this client only). A BillboardGui goes straight in PlayerGui
-- (inside a ScreenGui it would not show in the world); it is hidden on its own when the banner hides.
local marker = make("BillboardGui", {
	Name = "FreeGarageMarker",
	Size = UDim2.fromOffset(120, 60),
	StudsOffset = Vector3.new(0, 7, 0),
	AlwaysOnTop = true,
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

local function refresh()
	local show = onPlaza()
	gui.Enabled = show
	local post = show and nearestFreePost() or nil
	marker.Adornee = post
	marker.Enabled = post ~= nil
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
