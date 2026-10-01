# PR #14 review: security-review fixes

Branch `fix-security-review`, reviewed at commit `bc6420c` (#14 already merged with main). Diff reviewed: `origin/main..bc6420c` on `TycoonCore.lua`, `EmployeeServer.lua`, `PoachServer.lua`, `IpoServer.lua`. All `file:line` references point at `bc6420c`. Review only: no game code, Studio or Roblox was changed. This file lives on `claude/pr14-review`.

**Already checked earlier, not repeated here:** the merge with main, the order of the load-failure kick, the poach shield vs M5's free egg, and the duplicate check vs `grantEgg`.

## Severity scale

| Level | Meaning |
|---|---|
| Critical | A client can cheat, or player data or Robux value is lost or duplicated in a normal situation. Blocks the merge. |
| High | A bug that normal players will hit. Should block the merge. |
| Medium | A real bug in an uncommon situation, or the code does something different from what the PR promises. Fix before launch. |
| Low | A rare edge case, a confusing message, or a missing safety net. Fix when convenient. |

## 1. Going public with a poach deal open (`callOffForIpo`)

**Result: a poacher can't block, delay or profit from an IPO, and the refund is paid exactly once.** One Low (F3): the call-off happens before the IPO is saved.

| Question | Answer |
|---|---|
| Can a poacher block the IPO? | No. `PoachServer.isBusy` (`PoachServer.lua:640-651`) now counts only your own negotiation and your employees that are still being moved. A deal against you is called off. |
| Can a poacher delay it? | Only while a finished poach is still being saved (`inTransit`). That takes at most about 2 × 30 s if the DataStore keeps failing (`confirmSave`, `PoachServer.lua:202-217`). It can only happen once, because the victim gets `ShieldAfterPoach`. |
| Is the poacher refunded? | Yes. `cancel` (`PoachServer.lua:316-329`) adds `negotiation.cost` back. |
| Exactly once? | Yes. `cancel` only refunds if `poach.negotiation == negotiation`, and then clears it. The later `finish` timer returns at `:366`. A second `GoPublic` call is refused by `ipo.busy` and `data.ready`. |
| Is Cash created or lost? | No. Before the cancel, the poacher's save on disk holds either the old Cash, or Cash minus the cost plus `refund = cost` (`:773`). After it, memory holds the full Cash and `refund = nil`. All three states add up to the same total. |
| A Counter-Offer or accept arriving during the IPO | Nothing in `counterOffer` or `transfer` yields, so it can't interleave with `goPublic`, except during `commitIpo`. While `commitIpo` runs, `data.ready = false`. A new deal against you gets "Still loading" (`poachOf`, `:87`), your own remotes are refused (`:565`), and a Counter-Offer whose attacker is you waits (`:486`). Moves already in flight blocked the IPO up front through `inTransit`. |
| Poacher leaves while being refunded | `cancel` doesn't yield. If the poacher has already left, PoachServer's `PlayerRemoving` handler (`:879-887`) cancelled first. Either TycoonCore saved `refund = cost`, or the cancel ran before the save serialized. Both pay once. |
| IPO save fails after the call-off | The poacher keeps their refund, so no Cash is lost. But the victim's Counter-Offer is gone for good, and both sides were told the player "went public". See **F3**. |

### F3 (Low): the call-off runs before the IPO is saved
`IpoServer.lua:189` calls off the deals, and the save comes after it at `:203-211`. If `commitIpo` fails, the IPO doesn't happen. Even so, the victim has lost their one-time Counter-Offer, and the poacher was told "Deal called off: X went public." even though X didn't go public.
**Fix:** move `core.callOffPoachDeals(player)` after the `if not ok` check. It isn't needed before the save: during the save `data.ready = false`, so `protection()` already reports "Still loading". A negotiation that finishes in that window is cancelled and refunded by `finish` (`PoachServer.lua:376`), and no new deal can start.

## 2. Employee integrity (duplicates and losses)

**Result: no employee is lost from a save, and none is duplicated.** The duplicate check works: `addEmployee` checks the team and `pending` (`EmployeeServer.lua:423`), and loading keeps only the first copy of an ID (`:531-540`, `:553-554`). Loading puts team members before `outgoing` ones (`:574-579`), so the copy it keeps is the team one. That also fixes `reconcile` (`PoachServer.lua:304`), which used to remove only one copy. Two Lows remain on the new "the move failed, give it back" path.

| Case | What happens |
|---|---|
| Two poaches of the same employee at once | Impossible. There is one negotiation per target (`negotiations`, "Busy"), and `inTransit` blocks every other move and Counter-Offer until both saves are written. |
| Team full | `transfer` checks `hasFreeSlot(to)` before releasing anything (`PoachServer.lua:228`), so nothing moves. |
| `addEmployee(to)` refuses (ID already there) | New: the employee is given back to `from` (`:251-259`). See **F4** and **F5**. |
| Player leaves during a move | Unchanged by #14. `confirmSave` reads back the save written when they left, and `gained` + `reconcile` undo the move on their next join. |
| IPO during a move | Blocked: `isBusy` still checks `inTransit` on `employees` and `outgoing` (`:644-649`). |
| Counter-Offer for an employee still in `outgoing` | `addEmployee` now clears `outgoing` (`EmployeeServer.lua:426`), so the employee is saved once, not twice. This is correct. |

### F4 (Low): a poach that can't be completed after a successful roll keeps the poacher's Cash
`PoachServer.lua:399-406`. If `poached()` returns false, `finish` treats it as "defended": the Cash is spent and the cooldown is set. Before #14, `transfer` could not fail at that point. Now it can, through the new duplicate refusal at `:251`. That needs the poacher to already hold the same ID, so it only follows an earlier duplication bug. The poacher then loses Cash and gets a misleading "failed" result.
**Fix:** when `success` is true but `poached()` returns false, refund `negotiation.cost` (with a "deal fell through" message) instead of sending the "defended" result.

### F5 (Low): giving the employee back ignores whether it worked, and doesn't restore the exact old state
`PoachServer.lua:256` ignores the return value of `EmployeeServer.addEmployee(from, employee)`, and that function re-checks capacity (`EmployeeServer.lua:422`). A team can be over capacity: the Extra Employee Slots pass check timed out at join (M4 re-review finding 1), a Studio Debug "Ignore passes I really own", or a lowered perk. In that case the employee can't be given back. It stays only in `from`'s `outgoing` table: off the team, invisible and earning nothing for the rest of the session. It is still saved, and it comes back on the next join, so it is not lost. Even when the give-back works, the employee goes to the end of the list and `hiredAt` is reset to now. That doesn't matter today, because `hiredAt` is only saved, never read.
**Fix:** give it back without the capacity check: re-insert the original `employee` table at its old index and clear `team.outgoing[id]` (for example with a small `EmployeeServer.restoreEmployee`). Only reachable after F4's duplicate.
