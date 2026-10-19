-- FounderClient: the founder's activities and the calls at the desk, on screen (overhaul 2 phase 3, the owner's points 6
-- and 14). Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds everything by itself.
--
-- It only shows what the servers send and says which button was pressed: FounderServer (FounderRemotes) decides every
-- activity, TaskServer (TaskRemotes) every call. Nothing here decides a time, a grade or a reward.
--   Prompts     ProximityPrompts on this player's own stations (made here, so only the owner sees them; the positions are
--               the server's player attributes FounderDesk, FounderRack, FounderBoard): "Coding sprint" and "Investor
--               pitch" at the desk, "Fix the bug" at the Server Rack while its alarm rings, "Brainstorm" at the blackboard.
--               RequiresLineOfSight is off: the furniture's solid boxes would hide them.
--   The window  one activity at a time, in the middle of the screen (phone first: at most 360 x 320). It counts as a
--               window (PlayerGui "OpenPanel" = "Founder"): another window opening closes it (the activity is cancelled).
--   The desk    while a call waits, a board over the founder desk shows "Incoming call" with Answer and Decline. Answer
--               asks the server at once (the server grades it then), walks the founder to the desk, sits them down for
--               the answer (about 3 s, display only) and then shows the result. The phone tray (TaskClient) still
--               answers from anywhere. The sprint and the pitch also sit the founder at the desk while they run.
-- Nothing here says anything about odds or chance (D9).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local GuiService = game:GetService("GuiService")

local FounderConfig = require(ReplicatedStorage:WaitForChild("FounderConfig"))
if not FounderConfig.Enabled then
	return
end
local remotes = ReplicatedStorage:WaitForChild("FounderRemotes", 30)
if not remotes then
	return
end
local founderAction = remotes:WaitForChild("FounderAction")
local founderState = remotes:WaitForChild("FounderState")
local taskRemotes = ReplicatedStorage:WaitForChild("TaskRemotes", 10) -- calls (nil when the task engine is off)

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local TEXTS = FounderConfig.Texts
local PANEL_NAME = "Founder"
local ANSWER_SECONDS = 3 -- the founder's answer at the desk (display only: the server graded the call already)

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	card = Color3.fromRGB(44, 47, 58),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90),
	gold = Color3.fromRGB(255, 200, 60),
	late = Color3.fromRGB(230, 70, 60),
	close = Color3.fromRGB(200, 60, 60),
	grey = Color3.fromRGB(90, 94, 108),
}

-- UI helpers ------------------------------------------------------------------------------------------

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

local function fitText(inst, maxSize)
	inst.TextScaled = true
	make("UITextSizeConstraint", { MaxTextSize = maxSize, MinTextSize = 8, Parent = inst })
end

-- The window -------------------------------------------------------------------------------------------

local gui = make("ScreenGui", { Name = "FounderGui", ResetOnSpawn = false, ZIndexBehavior = Enum.ZIndexBehavior.Sibling, DisplayOrder = 4, Parent = playerGui })
local window = make("Frame", {
	Name = "Window", AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.new(0.92, 0, 0, 320),
	BackgroundColor3 = COLORS.panel, BackgroundTransparency = 0.05, Visible = false, Parent = gui,
})
round(window, 14)
make("UISizeConstraint", { MaxSize = Vector2.new(360, 320), Parent = window })
make("UIStroke", { Thickness = 2, Color = COLORS.gold, Transparency = 0.5, Parent = window })
local title = make("TextLabel", { Position = UDim2.fromOffset(14, 8), Size = UDim2.new(1, -72, 0, 30), BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold, TextColor3 = COLORS.gold, TextXAlignment = Enum.TextXAlignment.Left, Text = "", Parent = window })
fitText(title, 22)
local closeButton = make("TextButton", { AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -6, 0, 6), Size = UDim2.fromOffset(44, 44),
	BackgroundColor3 = COLORS.close, Font = Enum.Font.GothamBold, Text = "✕", TextColor3 = COLORS.text, Parent = window })
round(closeButton, 10)
fitText(closeButton, 22)
local help = make("TextLabel", { Position = UDim2.fromOffset(14, 52), Size = UDim2.new(1, -28, 0, 40), BackgroundTransparency = 1,
	Font = Enum.Font.Gotham, TextColor3 = COLORS.subtext, TextXAlignment = Enum.TextXAlignment.Left, TextWrapped = true, Text = "", Parent = window })
fitText(help, 16)
local track = make("Frame", { Position = UDim2.fromOffset(14, 96), Size = UDim2.new(1, -28, 0, 6), BackgroundColor3 = COLORS.card, BorderSizePixel = 0, Parent = window })
round(track, 3)
local fill = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = COLORS.buy, BorderSizePixel = 0, Parent = track })
round(fill, 3)

-- Up to 4 answer buttons: a list of 4 rows (sprint, pitch, brainstorm) or a 2 x 2 grid (the bug's fixes)
local buttons = {}
for i = 1, 4 do
	local button = make("TextButton", { BackgroundColor3 = COLORS.card, AutoButtonColor = true, Font = Enum.Font.Code, Text = "",
		TextColor3 = COLORS.text, TextWrapped = true, Visible = false, Parent = window })
	round(button, 10)
	fitText(button, 18)
	buttons[i] = button
end
local function layoutButtons(count, grid)
	for i, button in ipairs(buttons) do
		button.Visible = i <= count
		if grid then
			local col, row = (i - 1) % 2, (i - 1) // 2
			button.Position = UDim2.new(col * 0.5, col == 0 and 14 or 4, 0, 112 + row * 96)
			button.Size = UDim2.new(0.5, -18, 0, 88)
		else
			button.Position = UDim2.new(0, 14, 0, 112 + (i - 1) * 50)
			button.Size = UDim2.new(1, -28, 0, 46)
		end
	end
end

-- Pop-up message (bottom middle, like the call tray's)
local front = make("ScreenGui", { Name = "FounderFrontGui", ResetOnSpawn = false, DisplayOrder = 6, Parent = playerGui })
local toast = make("TextLabel", { AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -72), Size = UDim2.new(0.6, 0, 0, 48),
	BackgroundColor3 = COLORS.panel, BackgroundTransparency = 0.1, Font = Enum.Font.GothamBold, TextColor3 = COLORS.gold, Visible = false, Parent = front })
round(toast, 12)
fitText(toast, 20)
make("UISizeConstraint", { MaxSize = Vector2.new(340, 48), Parent = toast })
local toastToken = 0
local function showToast(text)
	if typeof(text) ~= "string" or text == "" then return end
	toastToken += 1
	local myToken = toastToken
	toast.Text = text
	toast.Visible = true
	task.delay(3, function()
		if toastToken == myToken then
			toast.Visible = false
		end
	end)
end

-- Sitting at the desk (display only) ----------------------------------------------------------------------

local seated = false
local function characterParts()
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if humanoid and root and humanoid.Health > 0 then
		return humanoid, root
	end
	return nil
end

-- Walks the founder to the desk and sits them on its chair. Returns false (and does nothing) when they are far away.
local function sitDown()
	if seated then return true end
	local humanoid, root = characterParts()
	local seat, stand = player:GetAttribute("FounderSeat"), player:GetAttribute("FounderStand")
	if not humanoid or typeof(seat) ~= "CFrame" or typeof(stand) ~= "Vector3" or (root.Position - stand).Magnitude > 70 then
		return false
	end
	seated = true
	if (root.Position - stand).Magnitude > 3 then
		humanoid:MoveTo(stand)
		local arrived = false
		local connection = humanoid.MoveToFinished:Connect(function() arrived = true end)
		local waited = 0
		while not arrived and waited < 6 and seated do
			waited += task.wait(0.1)
		end
		connection:Disconnect()
	end
	if not seated or not characterParts() then return false end
	local at = seat.Position + Vector3.new(0, 1.6, 0)
	root.Anchored = true
	root.CFrame = CFrame.lookAt(at, at - seat.LookVector) -- facing the desk (the garage's +Z from the chair)
	humanoid.Sit = true
	return true
end

local function standUp()
	if not seated then return end
	seated = false
	local humanoid, root = characterParts()
	if humanoid then
		root.Anchored = false
		humanoid.Sit = false
	end
end

-- The prompts on this player's stations ------------------------------------------------------------------------

local anchors = make("Folder", { Name = "FounderStations", Parent = workspace }) -- made here: only this player has it
local function anchorAt(name, up)
	local part = make("Part", { Name = name, Size = Vector3.new(1, 1, 1), Transparency = 1, Anchored = true, CanCollide = false,
		CanQuery = false, CanTouch = false, CastShadow = false, Parent = anchors })
	local prompt = make("ProximityPrompt", { RequiresLineOfSight = false, MaxActivationDistance = 10, HoldDuration = 0,
		Enabled = false, Parent = part })
	return { part = part, prompt = prompt, up = up }
end
local stations = {
	sprint = anchorAt("Desk", 3.5), pitch = anchorAt("DeskPitch", 5),
	bug = anchorAt("Rack", 4), brainstorm = anchorAt("Board", 3),
	dinner = anchorAt("Dinner", 3), -- the VIP Lounge's table (a fixed place in the world, phase 5)
}
stations.dinner.prompt.ActionText, stations.dinner.prompt.ObjectText = TEXTS.DinnerPrompt, "VIP Lounge"
do
	local at = FounderConfig.Dinner.at
	stations.dinner.part.Position = Vector3.new(at.x, at.y + stations.dinner.up, at.z)
end
stations.sprint.prompt.ActionText, stations.sprint.prompt.ObjectText = TEXTS.SprintPrompt, "Founder desk"
stations.pitch.prompt.ActionText, stations.pitch.prompt.ObjectText = TEXTS.PitchPrompt, "Founder desk"
stations.pitch.prompt.KeyboardKeyCode, stations.pitch.prompt.GamepadKeyCode = Enum.KeyCode.F, Enum.KeyCode.ButtonY
stations.bug.prompt.ActionText, stations.bug.prompt.ObjectText = TEXTS.BugPrompt, "Server Rack"
stations.brainstorm.prompt.ActionText, stations.brainstorm.prompt.ObjectText = TEXTS.BoardPrompt, "Blackboard"
local ATTRIBUTE = { sprint = "FounderDesk", pitch = "FounderDesk", bug = "FounderRack", brainstorm = "FounderBoard" }

local function placeStations()
	for which, station in pairs(stations) do
		local at = ATTRIBUTE[which] and player:GetAttribute(ATTRIBUTE[which])
		if typeof(at) == "Vector3" then
			station.part.Position = at + Vector3.new(0, station.up, 0)
		end
	end
end
for _, name in pairs(ATTRIBUTE) do
	player:GetAttributeChangedSignal(name):Connect(placeStations)
end
placeStations()

-- The alarm at the rack: a red light that blinks and a ping that repeats while it rings
local alarmLight = make("PointLight", { Color = Color3.fromRGB(255, 40, 40), Range = 18, Brightness = 0, Parent = stations.bug.part })
local alarmSound = make("Sound", { SoundId = "rbxasset://sounds/electronicpingshort.wav", Volume = 0.6, RollOffMaxDistance = 120, Parent = stations.bug.part })

-- State from the server ---------------------------------------------------------------------------------------

local state = nil -- FounderServer's last snapshot
local stateAt = 0
local activityKind = nil
local windowOpen = false
local busy = false -- a request is on its way

local function ask(action, arg)
	local called, ok, message, info = pcall(function()
		return founderAction:InvokeServer(action, arg)
	end)
	if not called then
		showToast("Couldn't reach the server. Please try again.")
		return false
	end
	if typeof(message) == "string" and message ~= "" then
		showToast(message)
	end
	return ok == true, info
end

local function otherWindowOpen()
	local open = playerGui:GetAttribute("OpenPanel")
	return open ~= nil and open ~= PANEL_NAME
end

local function setWindow(open)
	windowOpen = open
	window.Visible = open
	if open then
		playerGui:SetAttribute("OpenPanel", PANEL_NAME)
	elseif playerGui:GetAttribute("OpenPanel") == PANEL_NAME then
		playerGui:SetAttribute("OpenPanel", nil)
	end
	GuiService.TouchControlsEnabled = playerGui:GetAttribute("OpenPanel") == nil
end

local function refreshPrompts()
	local s = state
	local now = os.clock()
	local free = s ~= nil and s.activity == nil and not otherWindowOpen()
	local function ready(part)
		return part and part.on and (part.readyIn or 0) - (now - stateAt) <= 0
	end
	stations.sprint.prompt.Enabled = free and ready(s.sprint) or false
	stations.pitch.prompt.Enabled = free and s.pitch ~= nil or false
	stations.bug.prompt.Enabled = free and s.bug and s.bug.alarm or false
	stations.brainstorm.prompt.Enabled = free and ready(s.board) or false
	stations.dinner.prompt.Enabled = free and s.dinner ~= nil and s.dinner.ready == true or false
	if s and s.sprint and s.sprint.on and not stations.sprint.prompt.Enabled and free then
		-- cooling down: the prompt shows the wait instead (still visible, tapping it says "Ready in ...")
		local left = math.ceil((s.sprint.readyIn or 0) - (now - stateAt))
		stations.sprint.prompt.Enabled = left > 0
		stations.sprint.prompt.ActionText = left > 0 and string.format(TEXTS.Cooldown, left) or TEXTS.SprintPrompt
	else
		stations.sprint.prompt.ActionText = TEXTS.SprintPrompt
	end
end

local function showActivity(activity)
	local kind = activity.kind
	title.Text = kind == "sprint" and string.format("%s %d/%d", TEXTS.SprintTitle, activity.round, activity.of)
		or kind == "bug" and TEXTS.BugTitle
		or kind == "brainstorm" and TEXTS.BoardTitle
		or kind == "pitch" and string.format("%s · %s %d/%d", TEXTS.PitchTitle, activity.stage or "", activity.q, activity.of)
		or ""
	if kind == "sprint" then
		help.Text = TEXTS.SprintHelp
		layoutButtons(#activity.lines, false)
		for i, line in ipairs(activity.lines) do
			buttons[i].Text = line
			buttons[i].Font = Enum.Font.Code
		end
	elseif kind == "bug" then
		local steps = {}
		for i, name in ipairs(activity.order) do
			steps[i] = (i < activity.pos and "✓ " or (i == activity.pos and "▶ " or "")) .. name
		end
		help.Text = TEXTS.BugHelp .. ": " .. table.concat(steps, "  ")
		layoutButtons(#activity.buttons, true)
		for i, name in ipairs(activity.buttons) do
			buttons[i].Text = name
			buttons[i].Font = Enum.Font.GothamBold
		end
	elseif kind == "brainstorm" then
		help.Text = TEXTS.BoardHelp
		layoutButtons(#activity.ideas, false)
		for i, idea in ipairs(activity.ideas) do
			buttons[i].Text = idea.icon .. " " .. idea.name .. ": " .. idea.text
			buttons[i].Font = Enum.Font.GothamBold
		end
	elseif kind == "pitch" then
		help.Text = activity.question
		layoutButtons(#activity.options, false)
		for i, option in ipairs(activity.options) do
			buttons[i].Text = option
			buttons[i].Font = Enum.Font.GothamBold
		end
	end
	track.Visible = activity.limit ~= nil
end

local function applyState(s)
	state = s
	stateAt = os.clock()
	local activity = s.activity
	if activity then
		if otherWindowOpen() then
			task.spawn(ask, "Cancel") -- another window took the screen first
			return
		end
		showActivity(activity)
		if not windowOpen then
			setWindow(true)
		end
		if (activity.kind == "sprint" or activity.kind == "pitch") and activityKind ~= activity.kind then
			task.spawn(sitDown)
		end
	else
		if windowOpen then
			setWindow(false)
		end
		if activityKind == "sprint" or activityKind == "pitch" then
			standUp()
		end
	end
	activityKind = activity and activity.kind or nil
	local ringing = s.bug and s.bug.alarm or false
	if ringing and not alarmSound.IsPlaying then
		alarmSound.Looped = true
		alarmSound:Play()
	elseif not ringing then
		alarmSound:Stop()
		alarmLight.Brightness = 0
	end
	refreshPrompts()
end

founderState.OnClientEvent:Connect(function(kind, payload)
	if kind == "state" and typeof(payload) == "table" then
		applyState(payload)
	elseif kind == "alarm" then
		showToast(TEXTS.BugAlarm)
	end
end)

for which, station in pairs(stations) do
	station.prompt.Triggered:Connect(function()
		if busy or otherWindowOpen() then return end
		busy = true
		task.spawn(function()
			ask("Start", which)
			busy = false
		end)
	end)
end

for i, button in ipairs(buttons) do
	button.Activated:Connect(function()
		if busy or not windowOpen then return end
		busy = true
		task.spawn(function()
			ask("Pick", i)
			busy = false
		end)
	end)
end

closeButton.Activated:Connect(function()
	task.spawn(ask, "Cancel")
	setWindow(false)
	standUp()
end)

playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(function()
	if windowOpen and otherWindowOpen() then
		window.Visible = false
		windowOpen = false
		standUp()
		task.spawn(ask, "Cancel")
	end
	refreshPrompts()
end)

-- The calls at the desk ----------------------------------------------------------------------------------------

local deskBoard, deskAnswer, deskDecline, onCall, onCallFill
local waitingCall = nil -- the first waiting call's id (TaskServer's state)
local callsOn = false
local answeringAt = false
if taskRemotes then
	local taskAction = taskRemotes:WaitForChild("TaskAction")
	local taskState = taskRemotes:WaitForChild("TaskState")
	deskBoard = make("BillboardGui", { Name = "DeskCall", Adornee = stations.sprint.part, Size = UDim2.fromOffset(220, 96),
		StudsOffset = Vector3.new(0, 1.5, 0), MaxDistance = 80, AlwaysOnTop = false, Active = true, Enabled = false,
		ResetOnSpawn = false, Parent = playerGui })
	local card = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = COLORS.panel, BackgroundTransparency = 0.1, Parent = deskBoard })
	round(card, 12)
	local label = make("TextLabel", { Position = UDim2.fromOffset(8, 4), Size = UDim2.new(1, -16, 0, 34), BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold, Text = "📞 Incoming call", TextColor3 = COLORS.gold, Parent = card })
	fitText(label, 22)
	deskAnswer = make("TextButton", { Position = UDim2.new(0, 8, 0, 42), Size = UDim2.new(0.5, -12, 0, 48), BackgroundColor3 = COLORS.buy,
		Font = Enum.Font.GothamBold, Text = "Answer", TextColor3 = COLORS.text, Parent = card })
	round(deskAnswer, 10)
	fitText(deskAnswer, 20)
	deskDecline = make("TextButton", { Position = UDim2.new(0.5, 4, 0, 42), Size = UDim2.new(0.5, -12, 0, 48), BackgroundColor3 = COLORS.grey,
		Font = Enum.Font.GothamBold, Text = "Decline", TextColor3 = COLORS.text, Parent = card })
	round(deskDecline, 10)
	fitText(deskDecline, 20)

	-- "On the call..." over the founder's head while they answer (display only)
	onCall = make("BillboardGui", { Name = "OnCall", Size = UDim2.fromOffset(170, 44), StudsOffset = Vector3.new(0, 3, 0),
		AlwaysOnTop = false, Enabled = false, ResetOnSpawn = false, Parent = playerGui })
	local onCallCard = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = COLORS.panel, BackgroundTransparency = 0.15, Parent = onCall })
	round(onCallCard, 10)
	local onCallText = make("TextLabel", { Size = UDim2.new(1, 0, 0, 30), BackgroundTransparency = 1, Font = Enum.Font.GothamBold,
		Text = "📞 On the call...", TextColor3 = COLORS.text, Parent = onCallCard })
	fitText(onCallText, 18)
	local onCallTrack = make("Frame", { Position = UDim2.new(0, 10, 1, -10), Size = UDim2.new(1, -20, 0, 5), BackgroundColor3 = COLORS.card, BorderSizePixel = 0, Parent = onCallCard })
	onCallFill = make("Frame", { Size = UDim2.fromScale(0, 1), BackgroundColor3 = COLORS.buy, BorderSizePixel = 0, Parent = onCallTrack })

	local function refreshDesk()
		deskBoard.Enabled = callsOn and waitingCall ~= nil and not answeringAt and playerGui:GetAttribute("OpenPanel") == nil
	end
	taskState.OnClientEvent:Connect(function(kind, payload)
		if kind == "state" and typeof(payload) == "table" then
			callsOn = payload.on == true
			local first = typeof(payload.tasks) == "table" and payload.tasks[1]
			waitingCall = first and first.id or nil
			refreshDesk()
		end
	end)
	playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(refreshDesk)

	deskAnswer.Activated:Connect(function()
		local id = waitingCall
		if not id or answeringAt then return end
		answeringAt = true
		refreshDesk()
		local result = nil
		task.spawn(function() -- the server grades the answer now; the founder's walk and answer below are only the show
			local called, _ok, message = pcall(function()
				return taskAction:InvokeServer("Answer", id)
			end)
			result = called and (typeof(message) == "string" and message or "") or "Couldn't reach the server. Please try again."
		end)
		task.spawn(function()
			local sat = not seated and sitDown()
			if sat then
				local character = player.Character
				onCall.Adornee = character and character:FindFirstChild("Head")
				onCall.Enabled = onCall.Adornee ~= nil
				local started = os.clock()
				while os.clock() - started < ANSWER_SECONDS do
					onCallFill.Size = UDim2.fromScale((os.clock() - started) / ANSWER_SECONDS, 1)
					task.wait()
				end
				onCall.Enabled = false
				if activityKind == nil then
					standUp()
				end
			end
			local waited = 0
			while result == nil and waited < 5 do
				waited += task.wait(0.1)
			end
			showToast(result)
			answeringAt = false
			refreshDesk()
		end)
	end)
	deskDecline.Activated:Connect(function()
		local id = waitingCall
		if not id then return end
		task.spawn(function()
			pcall(function()
				taskAction:InvokeServer("Skip", id)
			end)
		end)
	end)
end

-- Countdown bar, the blinking alarm and the cooldown text (display only) ------------------------------------

local lastPromptRefresh = 0
RunService.Heartbeat:Connect(function()
	local now = os.clock()
	local activity = state and state.activity
	if windowOpen and activity and activity.limit then
		local left = math.max(0, (activity.left or 0) - (now - stateAt))
		local share = math.clamp(left / activity.limit, 0, 1)
		fill.Size = UDim2.fromScale(share, 1)
		fill.BackgroundColor3 = share < 0.25 and COLORS.late or COLORS.buy
	end
	if alarmSound.IsPlaying then
		alarmLight.Brightness = (math.floor(now * 3) % 2 == 0) and 6 or 0
	end
	if now - lastPromptRefresh > 0.5 then
		lastPromptRefresh = now
		refreshPrompts()
	end
end)

player.CharacterAdded:Connect(function()
	seated = false -- a new character stands
end)

task.spawn(function()
	ask("Sync")
end)
