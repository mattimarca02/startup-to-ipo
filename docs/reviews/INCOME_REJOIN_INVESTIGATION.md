# Income jump on rejoin: investigation (read-only, 2026-10-03)

Branch `income-rejoin-investigation`. No game code changed, no test added. **Result: cause NOT confirmed.** The repo code cannot produce the jump; below is what I ruled out, the best-fitting explanation (unproven), and a 5-minute Studio hand-test that decides it.

## 1. What the numbers say (before touching code)

Income is a pure function of saved state, recomputed every time: `floor((owned upgrades + employees) x pass multiplier x IPO multiplier)` (`TycoonCore.lua:120-135`). It is never saved or accumulated, so a jump needs a **state** change (an upgrade or an employee) or a **multiplier** change.

- **Multiplier:** I tried every pass combination (x1, 1.5, 2, 3) times every IPO multiplier (0 to 10 IPOs). Only **x1 for both readings** gives 43 and 83. That fits fake player -1: it owns no pass (`ShopServer.lua:166-175`, passes are not saved, `:436`). So the base income really rose by **exactly +40**.
- **43 is already odd.** Desk 1 + Coffee 2 + Laptop 5 + Sales Shark 20 = **28**. 43 = 28 + **15 (Server Rack)**. So a 4th upgrade was owned before the first rejoin, although the notes say "the Laptop bought". Something bought an upgrade without a deliberate step already in the first session.
- **+40 is exactly the Whiteboard** (cost 1,500, +40). A second Sales Shark would also be +20, so "2 x 20" needs two extra Sharks, which is the less natural reading.
- "Stayed 83 after rejoin 2" fits an upgrade that stays bought while the next one (Neon Logo, $5,000) is not yet affordable.

## 2. Ruled out (with evidence)

I ran the **real** `TycoonCore` plus the real `ShopServer`, `IpoServer`, `EmployeeServer`, `PoachServer`, `OnboardingServer`, `DailyServer` and all configs against a fake Roblox and a fake DataStore (same style of fakes as `tools/daily_test.py`, but the whole join/leave path, not marked fragments). Flow: join, buy pads, force a Rare hatch until Sales Shark, leave, rejoin x3, rejoin after 2 h.

| Case | Income before | after rejoins 1, 2, 3 |
|---|---|---|
| baseline, no passes (4 upgrades + Shark) | 43 | 43, 43, 43 |
| quick rejoin and 2 h later | 28 | 28 x4 |
| paid random items restricted (fixed hire order) | 43 | 43, 43, 43 |
| every pass owned (x3) | 129 | 129, 129, 129 |
| 2 ready eggs at leave, no Auto-Hatch | 43 | 43, 43, 43 |
| `PlayerAdded` fired twice for one player | 23 | live folder 23 (an orphan second `leaderstats` shows 0, never more) |

So: no employee is counted twice on load (`EmployeeServer.lua:567-577` skips a repeated ID; `owned` is a set, `TycoonCore.lua:640-642`); no saved Income plus recomputation exists; offline pay adds **Cash only** (`TycoonCore.lua:686-695`); the live path and the load path both end in the same `updateIncome` (`:182`, `:683`); no first-load-only migration touches upgrades or employees (`legacyValuation` and the free egg change valuation and incubators only). Poaching's `reconcile` (`PoachServer.lua:315-332`) only removes employees. Ready eggs hatching on join (`EmployeeServer.lua:818-823`) needs the **Auto-Hatch pass**, which player -1 does not own, and with every pass the multiplier would be x3, which the numbers exclude.

## 3. Best-fitting explanation (UNPROVEN): the green pad buys by touch

The pad sells the next upgrade the moment any part of the owner's character touches it with enough Cash (`TycoonCore.lua:173-185`). `refreshPad` rebuilds the pad **at the same spot** after each purchase (`:184`), so a character standing on or near it can buy the next upgrade too, with no click. That would explain the unexplained 4th upgrade before the first rejoin and a Whiteboard (+40, $1,500) after it, if the character touched the pad with $1,500+ on hand. In the harness, touching the pad after a rejoin turned 28 into 43 and later 43 into 83 by the same arithmetic, and every non-touch rejoin changed nothing. Against it: `teleportToPlot` lands the character 12 studs in front of the pad on purpose (`:564-571`), so I cannot show **why** it touched. Studio's fake character and spawn location are the unknown.

## 4. Real saves and the first publish

No duplicate can enter through the code path above, so a real save is safe from the "counted twice" reading. If the pad explanation is right, it is existing, intended behaviour (touch = buy), not a save bug; the only risk is the surprise, not lost data. Studio script drift is the other open candidate: a Studio copy older than PR #14 F2 (the duplicate-ID skip) would load duplicates. Check it in the hand-test.

## 5. Hand-test (Studio, one session; wipe `player_-1` first)

1. Test > Start Server and Clients, 1 player. Buy Desk, Coffee, Laptop with the pad, hire the Shark. Do **not** step on the pad again.
2. Command Bar set to **Server**, paste, and write down the output (`before`):
```lua
local p = game.Players:GetPlayers()[1]; local f = workspace[p.Name.."_Startup"]
local n, e = {}, {}
for _, c in f:GetChildren() do if c:GetAttribute("EmployeeId") then table.insert(e, c:GetAttribute("EmployeeId")) else table.insert(n, c.Name) end end
table.sort(n); print("Income", p.leaderstats.Income.Value, "Cash", p.leaderstats.Cash.Value)
print("parts:", table.concat(n, ",")); print("employees:", #e, table.concat(e, ","))
print("Studio EmployeeServer has the duplicate guard:", game.ServerScriptService.EmployeeServer.Source:find("Skipped a duplicate employee") ~= nil)
```
3. Wait 65 s (autosave) or leave once, then rejoin and run the same snippet (`after`).
4. Read the result: **a new part name (Whiteboard) and Cash down by 1,500** = the pad bought it (fix 1 below). **A new employee ID** = real duplication: also print the save with `game:GetService("HttpService"):JSONEncode(game:GetService("DataStoreService"):GetDataStore("StartupTycoon_v1"):GetAsync("player_-1"))` before and after and send both. **Guard line says false** = the Studio EmployeeServer is old: paste the repo file.

## 6. Minimal fixes (do NOT apply before the hand-test says which)

1. **If the pad bought it:** "In TycoonCore.lua, ignore BuyPad touches until 3 seconds after `teleportToPlot` has placed the character: set `data.padArmedAt = os.clock() + 3` there and return early in the pad's Touched handler while `os.clock() < data.padArmedAt`."
2. **If the Studio script was old:** no code change; paste the repo `EmployeeServer.lua` and `TycoonCore.lua` into Studio (CONTRIBUTING sync rule).
3. **If an employee really duplicated:** I could not reproduce it, so no fix is proposed; send the two JSON dumps.

## 7. Tests that would catch it

- A full-join group in `tools/daily_test.py` (join, buy, hire, leave, rejoin x3, assert `Income` equal each time): the scratch harness above is that test; it passed for every case in section 2. It would catch any save/load double count.
- A pad group: touching the pad right after spawn or rejoin buys nothing (needs fix 1).
- Not done: I did not add either to the suite, as asked.
