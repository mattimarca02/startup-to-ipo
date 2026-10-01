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
