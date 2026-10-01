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
