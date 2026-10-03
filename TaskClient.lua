-- TaskClient: the phone tray for customer calls (task engine, PR 1).
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts. It builds the screen by itself.
-- It only shows what TaskServer sends (TaskRemotes.TaskState) and asks the server to "Answer" a call.
-- It never decides a time, a reward or whether an answer counted: the countdown on a chip is for
-- display, the server's clock decides. Nothing here says anything about odds or chance (D9).
-- Outside Studio (PR 1) TaskConfig.isActive() is false: this script ends at once and shows nothing.
--
-- Layout (px, from the top-left of the GUI). IMPORTANT: every ScreenGui here keeps IgnoreGuiInset = false, so
-- the GUI is shorter than the device by Roblox's top bar (the size is not measured yet: the tests use 0, 36 and
-- 58 px). Everything at the top (HUD, Goals card) moves with the GUI's top; the pop-up lanes, the thumbstick and
-- the jump button hang from the GUI's bottom, so a taller bar squeezes the space between them.
-- The tray sits clear of the other HUD, of Roblox's touch controls (thumbstick x < 170 and y > H-170; jump
-- button x > W-150 and y > H-130) and of the bottom-center pop-up lanes (offsets -16, -72, -128, -184 and -240
-- from the bottom, 48 high each), as far as the space allows:
--   PORTRAIT_SPOT  chips at x 98, y 188 (320x568: 3 chips of 68x48, x 98-310, y 188-236; the line above them y 166-186).
--                  Under the Goals card (y 82-164 with 2 goals), right of the HUD column (x 12-88).
--                  Clear of every lane with a top bar of 0 or 36 px. With 58 px at 320x568 the -240 lane (the Daily
--                  pop-up) starts at y 222 and covers the lowest 14 px of the chips for as long as that pop-up shows.
--   LANDSCAPE_SPOT chips at x 10, y 92 (667x375: 3 chips of 52x48, x 10-174, y 92-140; the line above them y 70-90),
--                  right under the HUD button row and left of the valuation bar. Clear of everything with a top bar of 0.
--                  With 36 or 58 px the -184 lane (the Onboarding pop-up) starts at y 107 or 85 and the lane is
--                  wider than the gap, so it covers part of the chips for as long as that pop-up shows.
-- The full list of what the tray touches, by device size and top bar, is the ACCEPTED list in tools/daily_test.py
-- (TRAY_TESTS) and in docs/ACTIVE_LOOPS_PROPOSAL.md. Nothing fits everywhere (a 568x320 phone has no free gap at
-- all), so the tray draws BELOW every other pop-up (DisplayOrder -2): a pop-up is never hidden by it.
-- THE FINAL SPOTS MUST BE CONFIRMED IN STUDIO with Test > Device (320x568 and 667x375): change the two constants
-- PORTRAIT_SPOT and LANDSCAPE_SPOT below, nothing else. (Debug > Task stats shows the real TaskGui size.)
-- A window open (PlayerGui attribute "OpenPanel") hides the tray and tells the server to freeze the
-- waiting calls for a moment.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local GuiService = game:GetService("GuiService")

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
-- A screen of w x h pixels (the GUI's size, without the top bar) -> the tray's rectangle, the size of one chip
-- and the line above it. Short screens (phones held sideways, height under 460, the same switch as the HUD
-- buttons) and tall screens each have their own spot (see the layout notes at the top). Chips are 48 high
-- (the touch target minimum).
local CHIP_COUNT = 3
local CHIP_HEIGHT = 48
local CHIP_GAP = 4
local INFO_HEIGHT = 20
local INFO_GAP = 2
-- Portrait: right of the HUD column (x 98 on), just under the Goals card. Goals card bottom = 12 + 64 (valuation
-- bar) + 6 + (30 + 22 x goals + 8) = 164 with 2 goals; the line above the tray starts at y - 22 = 166, so each
-- extra goal (22 px) needs a bigger y here. The chips run to the right edge of the screen minus 10.
local PORTRAIT_SPOT = { x = 98, y = 188 } -- top-left corner of the chips
-- Landscape: the strip under the HUD button row (bottom y 70, where the line starts), left of the valuation bar.
-- Chips are a fixed 52 wide, so the tray is as narrow as a touch target allows (it stays out of the pop-up lanes
-- as far as it can).
local LANDSCAPE_SPOT = { x = 10, y = 92 } -- top-left corner of the chips
local LANDSCAPE_CHIP_WIDTH = 52
local function trayLayout(w, h)
	local left, top, chipWidth
	if h < 460 then
		left = LANDSCAPE_SPOT.x
		top = LANDSCAPE_SPOT.y
		chipWidth = LANDSCAPE_CHIP_WIDTH
	else
		left = PORTRAIT_SPOT.x
		top = PORTRAIT_SPOT.y
		chipWidth = math.clamp(math.floor((w - 10 - left - CHIP_GAP * (CHIP_COUNT - 1)) / CHIP_COUNT), 48, 104)
	end
	local width = chipWidth * CHIP_COUNT + CHIP_GAP * (CHIP_COUNT - 1)
	return {
		x = left, y = top, w = width, h = CHIP_HEIGHT, chipWidth = chipWidth, gap = CHIP_GAP,
		infoY = top - INFO_HEIGHT - INFO_GAP, infoH = INFO_HEIGHT,
	}
end
-- TRAY-END

-- The screen -------------------------------------------------------------------------

-- Under every window and under every other pop-up (DisplayOrder -2; the HUD buttons are at -1, the other
-- pop-ups at 0 or more), so the tray never hides a message. The tray's own message has a layer above.
local gui = make("ScreenGui", {
	Name = "TaskGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = -2,
	Parent = playerGui,
})
local front = make("ScreenGui", {
	Name = "TaskFrontGui",
	ResetOnSpawn = false,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	DisplayOrder = 5,
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
	Parent = front,
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

-- Studio only: the real size of this GUI and Roblox's top bar, to the Output and to the server (Debug > "Task
-- stats" prints them), so the owner can read the top bar that the layout tests only assume (0, 36 and 58 px).
local reportToken = 0
local lastReport = ""
local function reportSize(force)
	if not RunService:IsStudio() then return end
	reportToken += 1
	local myToken = reportToken
	task.delay(0.4, function()
		if reportToken ~= myToken then return end
		local size, inset = gui.AbsoluteSize, GuiService:GetGuiInset()
		local key = string.format("%dx%d top bar %d px", size.X, size.Y, inset.Y)
		if key == lastReport and not force then return end
		lastReport = key
		print("[TaskGui] AbsoluteSize " .. key .. " (GuiService:GetGuiInset)")
		local sizeAndBar = Vector3.new(size.X, size.Y, inset.Y)
		pcall(function()
			taskAction:InvokeServer("Layout", sizeAndBar)
		end)
	end)
end

gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(function()
	place()
	reportSize(false)
end)
place()

-- State from the server ----------------------------------------------------------------

local calls = {} -- waiting calls: { id, limit, endsAt (this device's clock, display only) }
local quiet = false
local chainMult = 1
local windowOpen = playerGui:GetAttribute("OpenPanel") ~= nil -- a window may already be open when this script starts
local serverPaused = false -- what the server last told us (state.paused) or accepted from us
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

-- PAUSE-START
-- (tools/daily_test.py runs the code between the PAUSE markers, so keep it free of Roblox calls.)
-- Does the server still have to hear about the window? Returns the value to send, or nil when the server
-- already agrees. Used at start (a window already open), after a refused request and on every state.
local function pauseToSend(windowOpen, serverPaused)
	if windowOpen == serverPaused then
		return nil
	end
	return windowOpen
end
-- PAUSE-END
local PAUSE_RETRY = 1 -- seconds before a refused or lost Pause request is sent again
local pauseBusy = false
local function syncPause()
	if pauseBusy then return end
	local wanted = pauseToSend(windowOpen, serverPaused)
	if wanted == nil then return end
	pauseBusy = true
	task.spawn(function()
		local called, ok = pcall(function()
			return taskAction:InvokeServer("Pause", wanted)
		end)
		pauseBusy = false
		local accepted = called and ok == true
		if accepted then
			serverPaused = wanted
		end
		-- Refused (rate limit, still loading) or no answer: try again until server and window agree.
		-- Accepted but the window changed meanwhile: send the newer value at once.
		if pauseToSend(windowOpen, serverPaused) ~= nil then
			task.delay(accepted and 0 or PAUSE_RETRY, syncPause)
		end
	end)
end

local function applyState(state)
	if typeof(state.paused) == "boolean" then
		serverPaused = state.paused
	end
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
	syncPause()
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
	syncPause()
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

-- First state: the server answers "Sync" with a state event (it says whether it is paused), and if a
-- window is already open the server hears about it right away
refresh()
task.spawn(function()
	pcall(function()
		taskAction:InvokeServer("Sync")
	end)
	syncPause()
	reportSize(true)
end)
