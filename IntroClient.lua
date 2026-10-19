-- IntroClient: the join cinematic and the fountain's water (overhaul 2 phase 5, the owner's points 2 and 3).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. Client only: it changes nothing on the server, saves
-- nothing and sends nothing.
--
-- The cinematic: once per session (a LocalScript in StarterPlayerScripts runs once), when the player first stands on the
-- plaza with the claim on, the camera flies about 7 s over the plaza (the arch, the fountain, the ring of garages) and
-- lands behind the player's character. Any tap, click or key skips it. It counts as a window while it plays (PlayerGui
-- "OpenPanel" = "Intro", taken only when no window has it, given back at the end), so the Daily window and the other
-- pop-ups wait. The camera always goes back to the player's own camera, also when something fails.
-- The fountain: a splash (a ParticleEmitter with Roblox's built-in default texture) on the fountain's jet and a soft
-- built-in water sound, made here, on this client only (the World model the server builds has neither: its checks allow
-- only plain Parts).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local LobbyConfig = require(ReplicatedStorage:WaitForChild("LobbyConfig"))

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local PANEL_NAME = "Intro"

-- INTROPLAN-START
-- (tools/intro_test.py runs the code between the INTROPLAN markers, so keep it free of Roblox calls.)
-- The flight, as { from the plaza's center: camera x, y, z, look at x, y, z, seconds to get there }. The plaza's south
-- (z below its center) is the arch's side; the fountain stands 50 north of the center. The last leg ends behind the
-- character (not in this table: it depends on where the character stands).
local SHOTS = {
	{ 0, 34, -78, 0, 22, -26, 0 }, -- start: in front of the arch, looking up at its attic
	{ 0, 30, -20, 0, 6, 50, 1.6 }, -- over the arch, the fountain ahead
	{ 26, 20, 50, 0, 5, 50, 1.6 }, -- round the fountain
	{ 0, 95, 10, 0, 0, 30, 1.8 }, -- high over the plaza: the ring of garages
}
local LAND_SECONDS = 1.8 -- the last leg, down behind the character
local LAND_BEHIND = { 0, 7, 14 } -- the landing, in the character's frame (above and behind)
local function introSeconds()
	local total = LAND_SECONDS
	for _, shot in ipairs(SHOTS) do
		total += shot[7]
	end
	return total
end
-- INTROPLAN-END

-- The fountain's water ------------------------------------------------------------------------------------------------

local function addFountainWater()
	local world = workspace:WaitForChild("World", 30)
	local decor = world and world:WaitForChild("Decor", 10)
	local fountain = decor and decor:WaitForChild("Fountain", 10)
	local jet = fountain and fountain:FindFirstChild("FountainSpout")
	if not jet or jet:FindFirstChild("Splash") then return end
	local splash = Instance.new("ParticleEmitter") -- Roblox's built-in default particle texture: no asset
	splash.Name = "Splash"
	splash.Color = ColorSequence.new(Color3.fromRGB(190, 230, 255))
	splash.LightEmission = 0.3
	splash.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 0.1) })
	splash.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1) })
	splash.Lifetime = NumberRange.new(0.8, 1.2)
	splash.Rate = 40
	splash.Speed = NumberRange.new(7, 10)
	splash.SpreadAngle = Vector2.new(14, 14)
	splash.Acceleration = Vector3.new(0, -22, 0)
	splash.EmissionDirection = Enum.NormalId.Top
	splash.Parent = jet
	local sound = Instance.new("Sound")
	sound.Name = "WaterSound"
	sound.SoundId = "rbxasset://sounds/impact_water.mp3"
	sound.Volume = 0.15
	sound.Looped = true
	sound.PlaybackSpeed = 0.6
	sound.RollOffMaxDistance = 60
	sound.RollOffMinDistance = 8
	sound.Parent = jet
	sound:Play()
end
task.spawn(function()
	local ok, err = pcall(addFountainWater)
	if not ok then
		warn("IntroClient: the fountain's water could not be added: " .. tostring(err))
	end
end)

-- The cinematic ----------------------------------------------------------------------------------------------------------

local function onPlaza()
	return player:GetAttribute("Garage") == 0
end

local function playIntro()
	local camera = workspace.CurrentCamera
	local character = player.Character or player.CharacterAdded:Wait()
	local root = character:WaitForChild("HumanoidRootPart", 10)
	if not camera or not root then return end
	local center = Vector3.new(LobbyConfig.PlazaCenter.x, 0, LobbyConfig.PlazaCenter.z)
	local tookPanel = false
	if playerGui:GetAttribute("OpenPanel") == nil then
		playerGui:SetAttribute("OpenPanel", PANEL_NAME)
		tookPanel = true
	end
	local skipped = false
	local skip = UserInputService.InputBegan:Connect(function(input)
		local kind = input.UserInputType
		if kind == Enum.UserInputType.Touch or kind == Enum.UserInputType.MouseButton1 or kind == Enum.UserInputType.Keyboard or kind == Enum.UserInputType.Gamepad1 then
			skipped = true
		end
	end)
	local oldType = camera.CameraType
	local ok, err = pcall(function()
		camera.CameraType = Enum.CameraType.Scriptable
		local function shotFrame(shot)
			return CFrame.lookAt(center + Vector3.new(shot[1], shot[2], shot[3]), center + Vector3.new(shot[4], shot[5], shot[6]))
		end
		camera.CFrame = shotFrame(SHOTS[1])
		for i = 2, #SHOTS do
			if skipped then break end
			local tween = TweenService:Create(camera, TweenInfo.new(SHOTS[i][7], Enum.EasingStyle.Sine, Enum.EasingDirection.InOut), { CFrame = shotFrame(SHOTS[i]) })
			tween:Play()
			local started = os.clock()
			while os.clock() - started < SHOTS[i][7] and not skipped do
				task.wait()
			end
			tween:Cancel()
		end
		if not skipped then
			local behind = root.CFrame * CFrame.new(LAND_BEHIND[1], LAND_BEHIND[2], LAND_BEHIND[3])
			local land = TweenService:Create(camera, TweenInfo.new(LAND_SECONDS, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
				{ CFrame = CFrame.lookAt(behind.Position, root.Position + Vector3.new(0, 2, 0)) })
			land:Play()
			local started = os.clock()
			while os.clock() - started < LAND_SECONDS and not skipped do
				task.wait()
			end
			land:Cancel()
		end
	end)
	skip:Disconnect()
	camera.CameraType = oldType == Enum.CameraType.Scriptable and Enum.CameraType.Custom or oldType
	camera.CameraSubject = character:FindFirstChildOfClass("Humanoid")
	if tookPanel and playerGui:GetAttribute("OpenPanel") == PANEL_NAME then
		playerGui:SetAttribute("OpenPanel", nil)
	end
	if not ok then
		warn("IntroClient: the cinematic stopped: " .. tostring(err))
	end
end

if LobbyConfig.ClaimEnabled then
	task.spawn(function()
		-- Wait (at most 20 s) until the player stands on the plaza and the world is built, then fly once
		local waited = 0
		while waited < 20 and not (onPlaza() and workspace:FindFirstChild("World") and player.Character) do
			waited += task.wait(0.25)
		end
		if onPlaza() and workspace:FindFirstChild("World") then
			task.wait(0.5)
			playIntro()
		end
	end)
end
