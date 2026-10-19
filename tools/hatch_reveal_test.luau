-- The real HATCHPANEL block of EmployeeClient.lua (ux lane, request U2 of the gameplay lane): while the hatch reveal
-- plays it holds the PlayerGui attribute "OpenPanel" as "Hatch", so TaskClient freezes the calls. tools/hud_test.py puts
-- one function in front of the scenarios: BLOCK (the block between "-- HATCHPANEL-START" and "-- HATCHPANEL-END",
-- given a fake playerGui), returning its setRevealShowing. Each scenario has its own "ran without an error" check, and
-- no other check reads the error: a mutant counts only when a check about "OpenPanel" fails.
local print_real = print
local passed, failed = 0, 0
local function check(name, cond, extra)
	if cond then passed += 1 else failed += 1; print_real("FAIL: " .. name .. (extra ~= nil and (" -- " .. tostring(extra)) or "")) end
end
local function signal()
	local s = { handlers = {} }
	function s.Connect(self, fn) table.insert(self.handlers, fn) return { Disconnect = function() end } end
	function s.Fire(self, ...) for _, fn in ipairs(table.clone(self.handlers)) do fn(...) end end
	return s
end
-- A PlayerGui with attributes that fire their changed signal only on a change (as Roblox does). `log` keeps every
-- value OpenPanel took, in order, so a scenario can see that it never went back to nil in the middle.
local function gui()
	local g = { attrs = {}, signals = {}, log = {} }
	function g.GetAttribute(self, k) return self.attrs[k] end
	function g.GetAttributeChangedSignal(self, k) self.signals[k] = self.signals[k] or signal() return self.signals[k] end
	function g.SetAttribute(self, k, v)
		if self.attrs[k] == v then return end
		self.attrs[k] = v
		if k == "OpenPanel" then table.insert(self.log, v == nil and "nil" or v) end
		if self.signals[k] then self.signals[k]:Fire() end
	end
	return g
end
local function start(openAtStart)
	local W = { pg = gui() }
	if openAtStart ~= nil then W.pg:SetAttribute("OpenPanel", openAtStart) end
	W.pg.log = {}
	local ok, res = pcall(BLOCK, W.pg)
	if ok then W.show = res else W.err = res end
	return W
end
local function run(W, fn, ...)
	if W.err or not W.show then return end
	local ok, err = pcall(fn, ...)
	if not ok and not W.err then W.err = err end
end
local function show(W, on) run(W, W.show, on) end
local function set(W, v) run(W, W.pg.SetAttribute, W.pg, "OpenPanel", v) end
local function panel(W) return W.pg:GetAttribute("OpenPanel") end
local function ranClean(W, label) check("block: ran without an error (" .. label .. ")", W.err == nil, W.err) end
local function log(W) return table.concat(W.pg.log, ",") end

do -- no window open: the reveal holds "Hatch" and gives it back
	local W = start(nil)
	show(W, true)
	check("no window: while the reveal plays OpenPanel is \"Hatch\" (TaskClient freezes the calls)", panel(W) == "Hatch", panel(W))
	show(W, false)
	check("no window: after the reveal OpenPanel is nil again (the calls run again)", panel(W) == nil, panel(W))
	check("no window: OpenPanel went Hatch then nil, nothing else", log(W) == "Hatch,nil", log(W))
	ranClean(W, "no window")
end

do -- the Eggs window is open (a hatch from its button): it keeps OpenPanel, before, during and after
	local W = start("Recruiting")
	show(W, true)
	check("window open: the reveal never takes OpenPanel from an open window (the Eggs window stays open)", panel(W) == "Recruiting", panel(W))
	show(W, false)
	check("window open: after the reveal the open window still has OpenPanel", panel(W) == "Recruiting", panel(W))
	check("window open: OpenPanel never changed", log(W) == "", log(W))
	ranClean(W, "window open")
end

do -- the open window closes during the reveal: the reveal takes OpenPanel at once, so the calls stay frozen
	local W = start("Recruiting")
	show(W, true)
	set(W, nil)
	check("window closed during the reveal: OpenPanel is \"Hatch\" again at once", panel(W) == "Hatch", panel(W))
	show(W, false)
	check("window closed during the reveal: after the reveal OpenPanel is nil", panel(W) == nil, panel(W))
	ranClean(W, "window closed during")
end

do -- a window opens during the reveal (the Daily window, the team window for a full team): it keeps OpenPanel
	local W = start(nil)
	show(W, true)
	set(W, "Daily")
	show(W, false)
	check("window opened during the reveal: the end of the reveal leaves that window's OpenPanel alone", panel(W) == "Daily", panel(W))
	ranClean(W, "window opened during")
end

do -- after the reveal the block is idle: a window closing later never brings "Hatch" back
	local W = start(nil)
	show(W, true)
	show(W, false)
	set(W, "Shop")
	set(W, nil)
	check("after the reveal: a window closing does not bring \"Hatch\" back", panel(W) == nil, panel(W))
	ranClean(W, "after")
end

do -- never shown: the block alone takes nothing
	local W = start(nil)
	set(W, "Shop")
	set(W, nil)
	check("never shown: the block alone never sets OpenPanel", panel(W) == nil and log(W) == "Shop,nil", log(W))
	ranClean(W, "never shown")
end

do -- two reveals in a row (two eggs hatched at once)
	local W = start(nil)
	show(W, true)
	show(W, false)
	show(W, true)
	check("two reveals: the second reveal holds \"Hatch\" again", panel(W) == "Hatch", panel(W))
	show(W, false)
	check("two reveals: and gives it back", panel(W) == nil, panel(W))
	ranClean(W, "two reveals")
end

print_real(string.format("%d passed, %d failed", passed, failed))
print_real("DONE")
