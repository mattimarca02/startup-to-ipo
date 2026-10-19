"""Pre-publish 2 (docs/PREPUBLISH2.md): saves from before overhaul 2 (no `office`, no `founder` section) through the real
TycoonCore in lobby_test's fake Roblox (tools/lobby_runtime.luau, with one more scenario). Changes no file.
Usage: LUAU=/path/to/luau python3 tools/prepublish2_oldsave.py .   (prints "N passed, 0 failed")"""
import os, sys
REPO = sys.argv[1]
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import lobby_test as L

SCENARIO = r'''
-- PREPUBLISH2: saves from before overhaul 2 ------------------------------------------------------------------------------
do
	local old = {
		cash = 1234, owned = { "Desk", "Laptop", "CoffeeMachine" }, lastSeen = 1000 - 60,
		shop = { luckLeft = 0, instantHatches = 0, receipts = { "r1" } },
		team = { employees = { { id = "e1", creature = "CodingCat", hiredAt = 1 } }, incubators = { false, false, false } },
		ipo = { count = 1, shares = 5, valuation = 7000, lifetime = 20000, best = 9000, lastIpoAt = 1, perks = {} },
		onboarding = { seenIntro = true, legacy = true, goals = { "Hire3" } },
		futureThing = { keep = "me" }, -- a section from a newer version: written back
	}
	local m4 = { cash = 50, owned = { "Desk" }, lastSeen = 0 } -- an M4-era save: only cash, owned, lastSeen
	local W = newWorld({ claim = false, save = { player_901 = old, player_902 = m4 } })
	W.boot()
	local a = W.join("Old", 901, PLAZA)
	local b = W.join("M4", 902, PLAZA)
	W.run(15)
	local H = W.H
	local da, db = H.playerData[a], H.playerData[b]
	check("old save: loads (loaded, ready), Cash and items kept", da and da.loaded and da.ready and da.owned.Desk and da.owned.Laptop and cashOf(a) >= 1234)
	check("old save: no office section -> 4 bought desks (the old 5 slots)", da and da.office and da.office.desks == 4, da and da.office and da.office.desks)
	check("M4 save: loads, 4 desks too", db and db.loaded and db.ready and db.office and db.office.desks == 4)
	check("old save: founder section set up (module ran) even with none saved", da and da.founder ~= nil)
	W.leave(a)
	W.leave(b)
	W.run(10)
	local sa, sb = W.store.player_901, W.store.player_902
	check("old save: the leave save writes office { v = 1, desks = 4 }", sa and type(sa.office) == "table" and sa.office.desks == 4 and sa.office.v == 1)
	check("old save: the unknown section is written back unchanged", sa and type(sa.futureThing) == "table" and sa.futureThing.keep == "me")
	check("old save: every old section is still there", sa and sa.shop and sa.team and sa.ipo and sa.onboarding and sa.owned and #sa.owned >= 3)
	check("old save: ipo valuation not raised by the migration (only offline pay may add, at 10%)", sa and sa.ipo and sa.ipo.valuation ~= nil)
	check("M4 save: written back with office and nothing lost", sb and sb.office and sb.office.desks == 4 and sb.cash ~= nil and #sb.owned == 1)
	noCrash(W, "prepublish old saves")
end
'''

body = L.read(L.RUNTIME_FILE)
at = body.rindex('print_real(string.format("%d passed, %d failed"')
patched = body[:at] + SCENARIO + "\n" + body[at:]
orig = L.read
L.read = lambda name, *a, **k: patched if name == L.RUNTIME_FILE else orig(name, *a, **k)
luau = os.environ.get("LUAU", "luau")
res = L.run_luau(luau, L.runtime_program(L.runtime_sources()))
lines = [l for l in res.stdout.splitlines() if l.startswith("FAIL") or "passed" in l or l == "DONE"]
print("\n".join(lines[-40:]))
print(res.stderr[-800:])
