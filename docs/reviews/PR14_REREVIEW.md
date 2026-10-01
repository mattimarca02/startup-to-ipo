# PR #14 re-review: the F1, F2 and F3 fixes

Branch `fix-security-review`, reviewed at commit `8de2f40`. Fix commits: F1 `c564c96`, F2 `b9c8c21`, F3 `6d5597f`. All `file:line` references point at `8de2f40`. Review only: no game code, Studio or Roblox was changed. This file lives on `claude/pr14-rereview`.

Severity scale: the same as `PR14_REVIEW.md` (Critical = cheat or data/Robux loss in a normal situation; High = normal players hit it; Medium = real bug in an uncommon situation; Low = rare edge case or missing safety net).

`tools/daily_test.py` (F1's 22 sanitizer checks) was **not run**: there is no `luau` binary in this environment. The checks were read, not executed.

## 1. F3: the call-off now runs after the IPO save

**Result: the refund is still paid exactly once, and no Cash is created or lost, in every case asked about.** One new Low (R3, Studio only) and one misleading comment and message (R4).

`IpoServer.lua:199-215`: `ipo.busy = true`, `data.ready = false`, `commitIpo` (yields inside `save`), then `data.ready = true`, then `core.callOffPoachDeals(player)`. Everything from the end of the save to the end of `goPublic` is synchronous, so nothing can run between `data.ready = true` and the call-off.

| Case | What happens | Refund |
|---|---|---|
| Save succeeds | `callOffForIpo` (`PoachServer.lua:657-672`) cancels `negotiations[V]`; `cancel` (`:316-329`) pays only if `poach.negotiation == negotiation`, then clears it. The later `finish` timer returns at `:366`. | Once |
| Save fails | `goPublic` returns at `:208-210` before the call-off. A running deal keeps going and ends normally. | Once (by `finish`) |
| A deal finishes during the save | `finish` → `protection(V)` → `poachOf(V)` is nil because `data.ready` is false → "Still loading" → `cancel` at `:382`. Then `callOffForIpo` finds nothing. Holds for success and failure. Only a **dummy** deal skips this check: see R3. | Once |
| Accept / counter during the save | A new deal against V: refused, `protection` says "Still loading" (`:154`). V's own remotes: refused by `onAction` (`:565`). A Counter-Offer where V is the attacker: refused "busy, try again", offer kept (`:486-488`). V's own Counter-Offer can't be sent (V's remotes are off) and is dropped after a successful save. | n/a |
| Poacher leaves mid-save | PoachServer's `PlayerRemoving` (`:880-888`) cancels with "You left": either Cash goes back into memory before TycoonCore's leave save, or the leave save already wrote `refund = cost` and the cancel only changes memory that is about to be thrown away. Then `callOffForIpo` finds nothing. | Once |
| Victim leaves mid-save | PoachServer's `PlayerRemoving` cancels "left the server". TycoonCore's leave `save` waits on `data.saving` (`TycoonCore.lua:268`), so `playerData[V]` is still set when `commitIpo` returns, and `goPublic` runs to the end synchronously before the leave save resumes. The leave save then writes the post-IPO state. | Once |
| Two deals against the same player | Impossible: `negotiations` holds one deal per target ("Busy", `:167`). `PoachDummyAttack` checks the same table. A Counter-Offer isn't a deal against V. | Once |

**Failed save: memory vs DataStore.** The DataStore keeps the last good save (from before the IPO). Memory is the pre-IPO state too: `commitIpo` returns at `TycoonCore.lua:339-341` before any reset, and `goPublic` returns before the call-off and the `ipo` update. Three things differ from "nothing happened": no income was earned during the save (expected), a deal that finished during the save was refunded instead of rolled (R4), and saves queued behind the lock (autosave, leaving) write the pre-IPO state afterwards (correct). If `SetAsync` errors but the write actually landed (a timeout after commit), the DataStore holds the IPO'd payload until the next autosave overwrites it with the non-IPO state. Both payloads are complete and consistent, so nothing is duplicated whichever survives. That was the same before F3.

### R3 (Low, new in F3, Studio only): a dummy deal that ends during the IPO save moves the employee, then errors
`PoachServer.lua:376`. A deal started with **Debug → PoachDummyAttack** has `ignoreShields = true`, so `finish` skips `protection()`, which is the only check that sees `data.ready = false`. If its timer ends during V's IPO save, it rolls (forced success), `transfer` releases the employee from V while the IPO payload is already serialized, and then `poached` does `table.insert(victimPoach.losses, now)` with `victimPoach = poachOf(V) = nil` (`:335-336`): an error, after the employee has left V's team. Before F3 the call-off ran before the save and cancelled the dummy deal, so this couldn't happen. Live servers have no dummy.
**Fix:** in `finish`, check `poachOf(target) == nil` (or `not data.ready`) as its own problem before the `ignoreShields` branch, for example `elseif not poachOf(target) then problem = name .. " is busy"`.

### R4 (Low): "A failed save leaves every deal as it was" isn't quite true, and the poacher gets the wrong reason
`IpoServer.lua:212-214`, `PoachServer.lua:376-377`, comment at `PoachServer.lua:653-656`. A deal whose timer ends during the save is cancelled even if the save then fails, and the poacher reads "Deal called off: X got protected." X wasn't protected: X was busy filing an IPO (which may have failed). Cash is right either way.
**Fix:** reword the comment ("a deal whose timer ends during the save is refunded, even if the save then fails"), and in `finish` give the un-ready case its own message (shared with R3's fix): "X is going public".

## 2. F1: type-checked cash, owned and lastSeen

**Result: every bad shape of the three fields is rejected without a kick, and no real Cash value can be clamped away.** Three Lows, all about what "sanitized" means for the rest of the join.

| Input | Result |
|---|---|
| `cash`: word, table, boolean, NaN, ±inf, negative | 0 with a warning (`TycoonCore.lua:196-201`) |
| `cash`: numeric string ("42"), fraction | 42; floored |
| `cash`: huge but finite | Clamped to 2^53, not to 0. Cash is an `IntValue` (64-bit), and no real save can get near 2^53: the best upgrade earns 120/s, and every spend is checked against Cash, so it can't go negative either. **No real progress is destroyed.** |
| `owned`: not a table | Empty list with a warning (`:202-212`) |
| `owned`: mixed junk | Strings kept, the rest skipped with a warning. Unknown upgrade names are kept and saved back (not lost). `owned` has always been a list (since `e381c06`), so the dictionary case can't come from old code. |
| `lastSeen`: string, NaN, ±inf, table | Dropped with a warning: no offline income (`:213-218`) |
| `lastSeen`: in the future | `math.clamp(... , 0, cap)` at `:566` gives 0 |
| The whole save isn't a table | Treated as no save (`:511-514`): see R5 |
| Nested bad values in other sections | Not F1's job, and still handled by each module: `ShopServer`, `EmployeeServer`, `PoachServer`, `OnboardingServer` and `DailyServer` all check `typeof` and skip bad entries. Exception: R8. |

The sanitizer runs inside the setup `pcall` and before any module, so the M5 / M6 "all modules loaded" gate is unchanged: `data.loaded = ok` is still set only at `:554`.

**M5 `hasProgress` (second free egg).** A sanitized value only zeroes Cash or upgrades that were garbage. A second free egg needs all of these at once: no `onboarding` section (a save from before M5), `cash` and `owned` both garbage, and no employees, eggs, IPO, Shares, receipts or poach notes (`OnboardingServer.lua:41-52, 255, 260`). Such a save had no real progress to lose, so the egg is harmless. The one real path to a "new player" is R5.

### R5 (Low): a save that isn't a table is treated as a brand-new player, and then overwritten
`TycoonCore.lua:511-514`. `saved = nil` keeps `ok = true`, so the player gets the new-player poach shield (`:544`, `ok and saved == nil`), the M5 free egg (`savedOnboarding` is nil and `hasProgress` is false), and their first save overwrites the unreadable value. CLAUDE.md says "never delete what you don't know". A non-table value can only come from a tool or a bug outside this code, so it's rare, but whatever was there is gone after one autosave.
**Fix:** keep the original value: `data.unknownSections.corruptSave = saved` before setting `saved = nil` (it is then written back next to the new save, so it can be recovered by hand), and pass `isNew = false` / count the player as `legacy` so no free egg or new-player shield is handed out on a save that only *looks* empty.

### R6 (Low): a bad `lastSeen` that is a valid number gives the full offline cap
`TycoonCore.lua:213-218, 564-571`. `lastSeen = 0`, `-1`, or `-1e12` pass the check (finite numbers), so `away` is clamped to the cap: 8 hours (plus the Night Shift perk) of offline income, which also goes through `addEarnings` and raises the IPO valuation. It needs a corrupt save, so it isn't a cheat, but it is a reward for bad data.
**Fix:** also require `rawSeen > 0` (any real `os.time()` is far above 0), or ignore values more than a year old.

### R7 (Low): no proof the 22 checks pass
`tools/daily_test.py:243-305`. The test copies the code between the `SANITIZE` markers and stubs `typeof` with `type`, which is fine for these inputs. It couldn't be run here (no `luau`). The checks read correctly, but run `python tools/daily_test.py` once before merging and paste the "N passed, 0 failed" line in the PR.

## 3. F2: GetDataStore retried at startup, live servers kick without a store

**Result: Studio vs live detection is sound and there is no double kick, but the startup retry yields before `PlayerAdded` is connected, and a server with no store never recovers.** Two Mediums.

| Question | Answer |
|---|---|
| How is Studio told from live? | `RunService:IsStudio()` (`TycoonCore.lua:34, 502`). It is true in every Studio session (Play, Play Here, Start Server/clients, Team Create) and false on every Roblox game server. It can't misfire either way. |
| Double kick? | No. The no-store kick at `:502-507` returns before setup, so the setup kick at `:548-552` can't follow. A kicked player's leave `save` returns at `:261` (`data.loaded` is false). |
| Kick loop? | Yes, server-wide: R2. |
| Can the retry delay or block joins? | Yes: R1. |

### R1 (Medium, new in F2): players who join during the startup retry are never set up, and never kicked
`TycoonCore.lua:22-32` vs `:460`. The retry loop yields (`task.wait(1)`, then `task.wait(2)`) at the top of the script, before the modules are required and before `Players.PlayerAdded:Connect` runs. TycoonCore has no catch-up loop over `Players:GetPlayers()`. Anyone who joins in those ~3 s (on a live server, often the very player whose join started the server; in Studio, the local tester) never gets a plot, `leaderstats` or `playerData`. They aren't kicked either, so it is exactly the silent broken session F2 set out to prevent, and every module's remotes are missing for those ~3 s. It only happens when `GetDataStore` fails, which is rare on live servers, but it is the normal case in an unpublished copy of the place in Studio.
**Fix:** after `Players.PlayerAdded:Connect(onPlayerAdded)`, add `for _, p in ipairs(Players:GetPlayers()) do task.spawn(onPlayerAdded, p) end` (name the handler first). Or, simpler, move the store lookup into a `getStore()` used by `load()` (see R2), so the top of the script never yields.

### R2 (Medium): a live server with no store kicks every joiner for its whole life
`TycoonCore.lua:22-39, 224, 502`. `store` is decided once at startup and never tried again. If `GetDataStore` failed for a few seconds at start, the server stays up and matchmaking keeps sending players to it (and back to it on rejoin, the message says "rejoin in a moment"), and every one of them is kicked until the server empties. The kick protects the save, so no data is lost, but the server is useless and players see repeated "couldn't load".
**Fix:** look the store up lazily: `local function getStore() if not store then local ok, s = pcall(DataStoreService.GetDataStore, DataStoreService, "StartupTycoon_v1"); if ok then store = s end end return store end`, called from `load`, `peekSave` and `save`. Keep the startup attempt (no `task.wait` needed). A server whose store comes back then heals on the next join. `GetDataStore` is not a budgeted request, so calling it per join is cheap.

## 4. Anything else new

- **Yields between a check and its use:** the only new yield is R1's. F3 moved the call-off past the save's yield, but everything after `data.ready = true` is synchronous (section 1). F1 adds no yield.
- **DataStore calls without `pcall`:** none. `GetDataStore` (`:23-25`), `GetAsync` (`:230`, `:248`) and `SetAsync` (`:302`) are all wrapped.
- **Remotes:** none added. `GoPublic` twice: `ipo.busy` and `data.ready`. `CounterOffer` twice: cleared before anything that could yield (`PoachServer.lua:495`).
- **M4 (IPO reset):** the reset is applied in `commitIpo` before the call-off, and the call-off only refunds the *poacher* and drops V's unsaved Counter-Offer, so the Cash reset can't swallow a refund.
- **M5 (onboarding):** see section 2 and R5.
- **M6 (daily claim):** a claim needs `data.ready` (`DailyServer.lua:219`), which is false for the whole IPO save and until the "all modules loaded" gate. F1's sanitizer runs before `DailyServer.setupPlayer` and doesn't touch `daily`. No change.

### R8 (Low, from before #14): the IPO section still accepts infinity
`IpoServer.lua:336-339`. `number()` rejects NaN and negatives but not `math.huge`, so a corrupt `ipo.count = inf` passes: the IPO can never be confirmed again (`ipoNumber ~= ipo.count + 1`), and `shares = inf` buys every perk. Not a kick and not reachable from a client, but it is the same class of bug F1 fixed. **Fix:** add `and value < math.huge` to `number()`.

## Summary

| Severity | Count | Findings |
|---|---|---|
| Critical | 0 | |
| High | 0 | |
| Medium | 2 | R1 joiners during the startup retry are never set up; R2 a server with no store kicks everyone forever |
| Low | 6 | R3 dummy deal during the IPO save (Studio); R4 misleading call-off comment and message; R5 non-table save treated as new and overwritten; R6 bad `lastSeen` pays the offline cap; R7 tests not run here; R8 IPO numbers accept inf |

**Top 3:** R1, R2, R5.

**Verdict: merge.** F3 is correct: the refund is paid exactly once in every case, and a failed save leaves memory and the DataStore consistent. F1 rejects every bad shape without a kick and never destroys a real Cash value. Both Mediums are in F2 and only happen when `GetDataStore` itself fails, which is rare on live servers. Fix R1 and R2 before launch (one small `getStore()` fixes both), and run `tools/daily_test.py` once before merging.
