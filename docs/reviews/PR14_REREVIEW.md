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
