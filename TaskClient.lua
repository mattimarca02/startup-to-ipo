-- TaskClient: the phone tray for customer calls (task engine, PR 1).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only shows what TaskServer sends (TaskRemotes.TaskState) and asks the server to "Answer" a call.
-- It never decides a time, a reward or whether an answer counted: the countdown on a chip is for
-- display, the server's clock decides. Nothing here says anything about odds or chance (D9).
-- Outside Studio (PR 1) TaskConfig.isActive() is false: this script ends at once and shows nothing.
--
-- Layout (px, from the top-left). The tray sits clear of the other HUD, of Roblox's touch controls
-- (thumbstick x < 170 and y > H-170; jump button x > W-150 and y > H-130) and of the pop-up lanes:
--   portrait 320x568:   3 chips of 68x48 at x 98-310, y 348-396
--   landscape 667x375:  3 chips of 104x48 at x 176-496, y 206-254
-- A window open (PlayerGui attribute "OpenPanel") hides the tray and tells the server to freeze the
-- waiting calls for a moment.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local TaskConfig = require(ReplicatedStorage:WaitForChild("TaskConfig"))
if not TaskConfig.isActive() then
	return
end
local remotes = ReplicatedStorage:WaitForChild("TaskRemotes", 30)
if not remotes then
	return
end
local taskAction = remotes:WaitForChild("TaskAction")
local taskState = remotes:WaitForChild("TaskState")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local TEXTS = TaskConfig.Texts

local COLORS = {
	panel = Color3.fromRGB(28, 30, 38),
	text = Color3.new(1, 1, 1),
	subtext = Color3.fromRGB(185, 190, 205),
	buy = Color3.fromRGB(0, 200, 90), -- same green as the buy pad
	gold = Color3.fromRGB(255, 200, 60),
	late = Color3.fromRGB(230, 70, 60), -- the bar when little time is left
	bar = Color3.fromRGB(20, 60, 40),
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

-- Where the tray goes ---------------------------------------------------------------

-- TRAY-START
-- (tools/daily_test.py runs the code between the TRAY markers, so keep it free of Roblox calls.)
-- A screen of w x h pixels -> the tray's rectangle, the size of one chip and the line above it.
-- Short screens (phones held sideways, height under 460, the same switch as the HUD buttons):
-- right of the thumbstick, left of the jump button. Tall screens: right of the HUD column and above
-- the thumbstick. Chips are 48 high (the touch target minimum).
local CHIP_COUNT = 3
local CHIP_HEIGHT = 48
local CHIP_GAP = 4
local INFO_HEIGHT = 20
local function trayLayout(w, h)
	local left, right, top
	if h < 460 then
		left = 176
		right = math.min(w - 156, left + 320)
		top = h - 169
	else
		left = 98
		right = w - 10
		top = h - 220
	end
	local chipWidth = math.clamp(math.floor((right - left - CHIP_GAP * (CHIP_COUNT - 1)) / CHIP_COUNT), 48, 104)
	local width = chipWidth * CHIP_COUNT + CHIP_GAP * (CHIP_COUNT - 1)
	return {
		x = left, y = top, w = width, h = CHIP_HEIGHT, chipWidth = chipWidth, gap = CHIP_GAP,
		infoY = top - INFO_HEIGHT - 2, infoH = INFO_HEIGHT,
	}
end
-- TRAY-END

-- The screen -------------------------------------------------------------------------

-- Under every window (DisplayOrder -1), like the HUD buttons
local gui = make("ScreenGui", {
	Name = "TaskGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = -1,
	Parent = playerGui,
})

local tray = make("Frame", {
	Name = "Tray",
	BackgroundTransparency = 1,
	Visible = false,
	Parent = gui,
})

local chips = {}
for i = 1, CHIP_COUNT do
	local button = make("TextButton", {
		Name = "Call" .. i,
		BackgroundColor3 = COLORS.buy,
		AutoButtonColor = true,
		Text = "",
		Visible = false,
		Parent = tray,
	})
	round(button, 10)
	make("UIStroke", { Thickness = 2, Color = COLORS.text, Transparency = 0.5, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = button })
	local icon = make("TextLabel", {
		Position = UDim2.fromOffset(0, 2),
		Size = UDim2.new(1, 0, 0, 24),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = "📞",
		TextColor3 = COLORS.text,
		Parent = button,
	})
	fitText(icon, 20)
	local label = make("TextLabel", {
		Position = UDim2.fromOffset(0, 26),
		Size = UDim2.new(1, 0, 0, 16),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		Text = TEXTS.Answer,
		TextColor3 = COLORS.text,
		Parent = button,
	})
	fitText(label, 14)
	local track = make("Frame", {
		Position = UDim2.new(0, 6, 1, -7),
		Size = UDim2.new(1, -12, 0, 4),
		BackgroundColor3 = COLORS.bar,
		BorderSizePixel = 0,
		Parent = button,
	})
	round(track, 2)
	local fill = make("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = COLORS.text,
		BorderSizePixel = 0,
		Parent = track,
	})
	round(fill, 2)
	chips[i] = { button = button, icon = icon, fill = fill, call = nil }
end

-- "Tap to resume": takes the place of the chips after a quiet spell
local resume = make("TextButton", {
	Name = "Resume",
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.1,
	AutoButtonColor = true,
	Font = Enum.Font.GothamBold,
	Text = TEXTS.Resume,
	TextColor3 = COLORS.gold,
	Visible = false,
	Parent = tray,
})
round(resume, 10)
make("UIStroke", { Thickness = 2, Color = COLORS.gold, Transparency = 0.4, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = resume })
fitText(resume, 16)

-- The line above the tray: the chain, or what the team handled
local info = make("TextLabel", {
	Name = "Info",
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBold,
	Text = "",
	TextColor3 = COLORS.gold,
	TextXAlignment = Enum.TextXAlignment.Left,
	Visible = false,
	Parent = gui,
})
fitText(info, 14)
make("UIStroke", { Thickness = 1, Color = Color3.new(0, 0, 0), Transparency = 0.4, Parent = info })

-- Pop-up message: bottom middle, a little narrower than the others so it clears the touch controls
local toast = make("TextLabel", {
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 1, -16),
	Size = UDim2.new(0.5, 0, 0, 48),
	BackgroundColor3 = COLORS.panel,
	BackgroundTransparency = 0.1,
	Font = Enum.Font.GothamBold,
	TextColor3 = COLORS.gold,
	Visible = false,
	ZIndex = 10,
	Parent = gui,
})
round(toast, 12)
fitText(toast, 20)
make("UISizeConstraint", { MaxSize = Vector2.new(300, 48), Parent = toast })

local toastToken = 0
local function showToast(text)
	toastToken += 1
	local myToken = toastToken
	toast.Text = text
	toast.Visible = true
	task.delay(2.5, function()
		if toastToken == myToken then
			toast.Visible = false
		end
	end)
end

local function place()
	local screen = gui.AbsoluteSize
	local layout = trayLayout(screen.X, screen.Y)
	tray.Position = UDim2.fromOffset(layout.x, layout.y)
	tray.Size = UDim2.fromOffset(layout.w, layout.h)
	for i, chip in ipairs(chips) do
		chip.button.Position = UDim2.fromOffset((i - 1) * (layout.chipWidth + layout.gap), 0)
		chip.button.Size = UDim2.fromOffset(layout.chipWidth, layout.h)
	end
	resume.Position = UDim2.fromOffset(0, 0)
	resume.Size = UDim2.fromOffset(layout.w, layout.h)
	info.Position = UDim2.fromOffset(layout.x, layout.infoY)
	info.Size = UDim2.fromOffset(layout.w, layout.infoH)
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(place)
place()

-- State from the server ----------------------------------------------------------------

local calls = {} -- waiting calls: { id, limit, endsAt (this device's clock, display only) }
local quiet = false
local chainMult = 1
local windowOpen = false
local answering = {} -- ids already tapped, until the server's next state
local handledText, handledUntil = "", 0 -- "Team handled 4 calls", shown for a few seconds

-- The line above the tray: what the team handled for a moment, else the chain
local function updateInfo()
	local text = ""
	if os.clock() < handledUntil then
		text = handledText
	elseif chainMult > 1 then
		text = string.format("x%.1f chain", chainMult)
	end
	info.Text = text
	info.Visible = not windowOpen and text ~= ""
end

local function refresh()
	local showTray = not windowOpen
	tray.Visible = showTray
	updateInfo()
	for i, chip in ipairs(chips) do
		chip.call = calls[i]
		chip.button.Visible = showTray and chip.call ~= nil
	end
	resume.Visible = showTray and quiet and #calls == 0
end

local function applyState(state)
	calls = {}
	local now = os.clock()
	for _, call in ipairs(state.tasks or {}) do
		if #calls < CHIP_COUNT then
			table.insert(calls, { id = call.id, limit = math.max(0.1, call.limit), endsAt = now + call.left })
		end
	end
	quiet = state.quiet == true
	chainMult = state.mult or 1
	answering = {}
	refresh()
end

taskState.OnClientEvent:Connect(function(kind, payload)
	if kind == "state" then
		if typeof(payload) == "table" then
			applyState(payload)
		end
	elseif kind == "handled" then
		if typeof(payload) == "number" then
			handledText = string.format(TEXTS.Handled, payload, payload == 1 and "call" or "calls")
			handledUntil = os.clock() + 5
			updateInfo()
			task.delay(5.1, updateInfo)
		end
	end
end)

-- Taps ---------------------------------------------------------------------------------

for _, chip in ipairs(chips) do
	chip.button.Activated:Connect(function()
		local call = chip.call
		if not call or answering[call.id] then return end
		answering[call.id] = true
		task.spawn(function()
			local called, _ok, message = pcall(function()
				return taskAction:InvokeServer("Answer", call.id)
			end)
			if called and typeof(message) == "string" and message ~= "" then
				showToast(message)
			elseif not called then
				showToast("Couldn't reach the server. Please try again.")
			end
		end)
	end)
end

resume.Activated:Connect(function()
	task.spawn(function()
		pcall(function()
			taskAction:InvokeServer("Start")
		end)
	end)
end)

-- A window hides the tray and freezes the waiting calls (the server limits how long)
local function onPanelChanged()
	local open = playerGui:GetAttribute("OpenPanel") ~= nil
	if open == windowOpen then return end
	windowOpen = open
	refresh()
	task.spawn(function()
		pcall(function()
			taskAction:InvokeServer("Pause", open)
		end)
	end)
end
playerGui:GetAttributeChangedSignal("OpenPanel"):Connect(onPanelChanged)

-- Countdown bars and the ringing phone (display only)
RunService.Heartbeat:Connect(function()
	if windowOpen or #calls == 0 then return end
	local now = os.clock()
	for _, chip in ipairs(chips) do
		local call = chip.call
		if call then
			local left = math.max(0, call.endsAt - now)
			local share = math.clamp(left / call.limit, 0, 1)
			chip.fill.Size = UDim2.fromScale(share, 1)
			chip.fill.BackgroundColor3 = share < 0.25 and COLORS.late or COLORS.text
			chip.icon.Rotation = left > 0 and math.sin(now * 18) * 10 or 0
		end
	end
end)

-- First state: the server answers "Sync" with a state event
task.spawn(function()
	pcall(function()
		taskAction:InvokeServer("Sync")
	end)
end)
