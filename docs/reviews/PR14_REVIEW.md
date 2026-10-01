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

## Fix status

| Finding | Status | Commit |
|---|---|---|
| F1 corrupt save locks the player out | Fixed: `cash`, `owned` and `lastSeen` are type-checked on load (bad values give safe defaults and a warning); 22 checks in `tools/daily_test.py` | c564c96 |
| F2 no DataStore on a live server | Fixed: `GetDataStore` is retried 3 times at startup; on a live server with no store, joining players are kicked; Studio keeps playing unsaved with a clear warning | b9c8c21 |
| F3 call-off before the IPO save | Fixed: deals are called off only after the IPO save succeeded | 6d5597f |
| F4 failed poach keeps the Cash | Skipped, added to the M9 list | 81fa904 |
| F5 give-back ignores capacity | Skipped, added to the M9 list | 81fa904 |
| F6 Studio kick with API access off | Skipped: no code change; documented in ROADMAP and CONTRIBUTING | d9a6157 |
| F7 retry budget | Skipped, added to the M9 list | 81fa904 |
| F8 misleading comment | Skipped, added to the M9 list | 81fa904 |

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
**Status: Fixed in 6d5597f.**
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
**Status: Skipped, in the M9 list (81fa904).**
`PoachServer.lua:399-406`. If `poached()` returns false, `finish` treats it as "defended": the Cash is spent and the cooldown is set. Before #14, `transfer` could not fail at that point. Now it can, through the new duplicate refusal at `:251`. That needs the poacher to already hold the same ID, so it only follows an earlier duplication bug. The poacher then loses Cash and gets a misleading "failed" result.
**Fix:** when `success` is true but `poached()` returns false, refund `negotiation.cost` (with a "deal fell through" message) instead of sending the "defended" result.

### F5 (Low): giving the employee back ignores whether it worked, and doesn't restore the exact old state
**Status: Skipped, in the M9 list (81fa904).**
`PoachServer.lua:256` ignores the return value of `EmployeeServer.addEmployee(from, employee)`, and that function re-checks capacity (`EmployeeServer.lua:422`). A team can be over capacity: the Extra Employee Slots pass check timed out at join (M4 re-review finding 1), a Studio Debug "Ignore passes I really own", or a lowered perk. In that case the employee can't be given back. It stays only in `from`'s `outgoing` table: off the team, invisible and earning nothing for the rest of the session. It is still saved, and it comes back on the next join, so it is not lost. Even when the give-back works, the employee goes to the end of the list and `hiredAt` is reset to now. That doesn't matter today, because `hiredAt` is only saved, never read.
**Fix:** give it back without the capacity check: re-insert the original `employee` table at its old index and clear `team.outgoing[id]` (for example with a small `EmployeeServer.restoreEmployee`). Only reachable after F4's duplicate.

## 3. Load retry and kick

**Result: the retry is safe. No half-loaded player is ever saved, and a double join gains nothing.** Two Mediums: a corrupt save still locks the player out, and the "never play unsaved" promise has a gap when the whole DataStore is missing.

| Question | Answer |
|---|---|
| Save from a half-loaded player during the ~6 s of retries | Impossible. `data.loaded` is false until `TycoonCore.lua:494`, so `save()` returns at `:207`. Autosave, `BindToClose` and leaving all write nothing. Every other module loop skips the player because it has no `data.ready` or `data.poach` yet. |
| Leaving during the retry | `load` stops retrying when `player.Parent` is nil (`:185`). PlayerRemoving clears `playerData`, and the check at `:449` returns before the kick or any setup. |
| Double join | Same server: a rejoin is a new Player object, and the old thread returns at `:449`. Two servers: the same race as before #14 (there is no session lock). The extra wait doesn't make it worse, because a kicked session never saves. |
| Is the kick message safe? | Yes. It's a constant string with no player data, and nothing is saved, so "your progress is safe" is true for a DataStore outage. |

### F1 (Medium, from before #14, still open): a corrupt save kicks the player every time they join
**Status: Fixed in c564c96.**
`TycoonCore.lua:458-459`: `cash.Value = saved.cash or 0` and `ipairs(saved.owned or {})` still have no type checks (M4 re-review finding 2). A bad value makes the setup `pcall` fail, which kicks the player (`:488-492`). #14 now reuses that kick path, and its message, "Please rejoin in a moment: your progress is safe", promises something a rejoin can't deliver: the player is locked out for good. The retry doesn't cause this (`GetAsync` succeeds) and doesn't fix it.
**Fix (M4 re-review):** use `tonumber(saved.cash) or 0` and check `typeof(saved.owned) == "table"`, skipping bad values with a warning, as CLAUDE.md requires.

### F2 (Medium): with no DataStore at all, a live server still runs every session without saving
**Status: Fixed in b9c8c21.**
`TycoonCore.lua:16-22, 175, 450`. If `GetDataStore` fails when the server starts, `store` is nil. `load` then returns `(nil, false)`, but the kick is skipped because it requires `store and not ok`. Every player on that server plays a fresh, never-saved session with no warning. Poaching (`PoachServer.lua:156, 434`) and IPO (`IpoServer.lua:174`) are refused for everyone. #14's ROADMAP line promises "no silent unsaved session", and this path breaks that promise. `GetDataStore` rarely fails on live servers, but when it does, every player on that server loses their whole session.
**Fix:** at startup, retry `GetDataStore` a few times. If `store` is still nil and `not RunService:IsStudio()`, kick joining players with `LOAD_FAILED_MESSAGE`. Keep the current "play unsaved" behaviour only in Studio.

### F6 (Low, check in Studio): in a published place with Studio API access off, playtests now get kicked
**Status: Skipped: no code change, documented in ROADMAP and CONTRIBUTING (d9a6157).**
`TycoonCore.lua:175-189, 450`. In a published place, `GetDataStore` usually works even with API access off, but `GetAsync` fails. Before #14 you played unsaved, and the warning told you to turn on API access. Now you're kicked after about 6 s of retries in every F5 playtest. Turning on API access fixes it, but beginners will see "Your startup couldn't load".
**Fix:** in `RunService:IsStudio()`, don't kick: leave `data.loaded = false` (play unsaved) and keep the warning. Confirm with one playtest with API access off.

### F7 (Low): during an outage, the retry triples load requests
**Status: Skipped, in the M9 list (81fa904).**
`TycoonCore.lua:176-187`. During a DataStore outage, every join and rejoin makes three `GetAsync` calls, so kicked players who rejoin use up the server's request budget faster.
**Fix (optional):** check `DataStoreService:GetRequestBudgetForRequestType(Enum.DataStoreRequestType.GetAsync)` before each retry, or keep it at 3 and accept it.

## 4. Poaching blocked when a save didn't load

**Result: it can't be used to grief anyone or to dodge a deal.** `data.loaded` is set only by the server (`TycoonCore.lua:494`), and a client can't change it. On a live server, a player with `loaded = false` is either still loading or about to be kicked: a failed read kicks at `:450-454` and a failed setup kicks at `:488-492`. A loading player is already hidden by `poachOf` (`data.ready` is false), so the new branches in `protection()` (`PoachServer.lua:155-158`) and `counterOffer` (`:483-485`) only matter when `store` is nil (F2, or Studio). There they correctly stop moves that could never be saved. A target can't look "unloaded" to stop a deal that's already running, because `finish` sees that state as "Still loading" and refunds the poacher.

One side effect: in an unpublished Studio place, you can't poach the Debug dummy (`:434`), although the dummy can still poach you (`PoachDummyAttack` skips `start`). Test poaching in the published place with API access on (F6).

## 5. Interaction with M5 (onboarding) and M6 (daily rewards)

**Result: no problems.**

| Situation | Free egg (M5) | Daily claim (M6) | New-player poach shield |
|---|---|---|---|
| Normal join | `grantFreeEgg` runs inside setup, after `PoachServer.setupPlayer`, so `data.poach` exists and the shield is raised. | The claim needs `data.ready` (`DailyServer.lua:219`). | Set at setup time: `ok and saved == nil` (`TycoonCore.lua:483`). |
| Join delayed by retries | Same. `ok` is true after a successful retry, so OnboardingServer sees the right new/old state. | Same. | Starts when setup runs, after the delay, so the player gets the full 15 minutes of play. |
| Failed load | Kicked before any module runs: no egg, no claim, nothing saved. | Same. | Same. |
| IPO | `grantEgg` and the daily egg both need `data.ready`, which is false while the IPO saves. Neither touches poach state. | Same. | `callOffForIpo` doesn't change `shieldUntil`, and the IPO resets don't include the shield. |

The duplicate check in `addEmployee` doesn't affect hatching: `hatch` and `resolvePending` insert directly, with fresh GUIDs.

## 6. Anything else new

- **Remotes:** #14 adds none. `GoPublic` sent twice is refused by `ipo.busy` and `data.ready`. `CounterOffer` sent twice: the first call clears `poach.counterOffer` before anything that could yield (`PoachServer.lua:495`).
- **DataStore calls:** the new `GetAsync` retry is inside `pcall` (`TycoonCore.lua:177`). No new unprotected calls.
- **Yields between a check and its use:** `goPublic` checks `isPoachBusy` and calls `callOffPoachDeals` without yielding. The only yield is inside `commitIpo`, and by then `data.ready = false` has closed every way in (section 1). `counterOffer` and `transfer` don't yield between their checks and the move. The saves are deferred, behind `inTransit`.
- **F8 (Low): a misleading comment.** **Status: Skipped, in the M9 list (81fa904).** The comment on `PoachServer.isBusy` (`PoachServer.lua:637-639`) says "a poacher can never stop someone's IPO". A finished poach still holds the IPO for up to ~60 s while it saves (section 1). That's harmless, but say so in the comment.

## Summary

| Severity | Count | Findings |
|---|---|---|
| Critical | 0 | |
| High | 0 | |
| Medium | 2 | F1 corrupt save locks the player out (from before #14, still open); F2 no DataStore on a live server means a silent unsaved session |
| Low | 6 | F3 call-off before the IPO save; F4 failed poach keeps the Cash; F5 give-back ignores capacity; F6 Studio kick with API access off; F7 retry budget; F8 comment |

**Top 3:** F2, F1, F3.

**Verdict: merge.** #14 introduces nothing Critical or High. The IPO call-off refunds exactly once, the duplicate checks hold, and the retry never saves a half-loaded player. Fix F1 and F2 before launch, and F3 when convenient. Also check F6 in Studio before the 2-client Mac tests.
