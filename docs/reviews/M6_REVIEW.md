# M6 review: daily rewards

Branch `milestone-6-daily-rewards`. Code reviewed at commit `1c855ca` (diff `main...1c855ca`). All `file:line` references point at that commit. Review only: no game code, Studio or Roblox was changed. This file lives on `claude/m6-review`.

Finding numbers here (F1, F2, ...) are this review's own. "M4 F9", "M4 F10" and "M5 F8" mean the findings in the earlier reviews in `docs/reviews/`.

**Not repeated here** (already passed in a Studio play session): double claim, rejoin, grace days, full incubators, Day 7 Shares not doubled, IPO keeps the streak, malformed remote calls. This review looks for what a playtest can't reach: races, clocks, two servers, old code, and screen sizes.

## Severity scale

| Level | Meaning |
|---|---|
| Critical | A client can cheat, or player data or Robux value is lost or duplicated in a normal situation. Blocks the merge. |
| High | A bug that normal players will hit. Should block the merge. |
| Medium | A real bug in an uncommon situation, or the code does something different from what the plan or ROADMAP promises. Fix before launch. |
| Low | A rare edge case, a confusing message, or a safety net that's missing. Fix when convenient. |

## 1. Save integrity

**Result: no partial save is possible, and the "nothing yields" claim is true.** The `daily` section follows the same rules as `onboarding`.

| Question | Answer |
|---|---|
| Is DailyServer inside the M4 F9 load gate? | Yes. `DailyServer.setupPlayer` runs last inside the setup `pcall` (`TycoonCore.lua:466`); `data.loaded` is set only after it (`TycoonCore.lua:474`). |
| Can a save be written during load? | No. `save()` refuses until `data.loaded` (`TycoonCore.lua:199`) and refuses while `data.daily` is missing (`TycoonCore.lua:200`). Autosave, leaving, `BindToClose` and the claim's own save all go through `save()`. |
| After a slow load (pass checks in `ShopServer.setupPlayer` yield)? | Same gate. `DailyServer.setupPlayer` itself does no DataStore call and doesn't yield, so it can't stretch the gate. If the player left while loading, `TycoonCore.lua:468` returns before `data.loaded` is set. |
| If daily setup errors? | `data.daily` is assigned at `DailyServer.lua:274`, then `publish` runs (`:275`). An error in either fails the `pcall`, kicks the player and `data.loaded` is never set (`TycoonCore.lua:469-473`). The DataStore copy stays as it was. |
| `BindToClose` | Unchanged (`TycoonCore.lua:540-544`). A claim's save in flight holds the lock (`TycoonCore.lua:206-209`); the shutdown save waits behind it and writes the same marker and reward. |
| Old saves with no `daily` section | `savedDaily == nil` → defaults `0/0/0/0` (`DailyServer.lua:237-245`): Day 1 is claimable. Nothing is written at load. |
| Bad values inside the section | Each known field must be a finite whole number ≥ 0, else skipped with `warn` (`DailyServer.lua:247-256`). A non-table section is replaced by defaults with a `warn` (`:262-263`). Unknown fields are kept in `daily.unknown` and written back (`:257-261`, `:288-292`). Matches CLAUDE.md. |
| Old code (M5, after the M4 F2 fix) | `main`'s `KNOWN_SECTIONS` has no `daily`, so a rollback to M5 writes the section back unchanged via `unknownSections`. The streak survives. |
| Code from before the M4 F2 fix | Would drop the section. Publish M6 with **Shut down all servers** (new section), as for M4 and M5. ROADMAP/README should say so at publish time (see F8). |
| `claim()`: "nothing yields between check and set" | **True.** Between `status()` (`DailyServer.lua:151`) and the marker (`:188-191`) the code calls `EmployeeServer.grantEgg` → `freeIncubator`, `startEgg` → `refreshIncubator`, `push` (`FireClient`), then `DailyConfig.cashFor`, `IpoServer.grantShares` → `publish` (`SetAttribute`). None of these wait. The only yield is `core.save` at `:205`, after the marker. A second request during that save sees `now <= lastClaimDay` and is refused. |
| Reward and marker saved apart? | Impossible: both live in the same in-memory state and every save serializes both. If the claim's save fails, the claim still answers success (`:205-209`) and the next autosave or leave save writes both. If *every* save this session fails, both are lost together (nothing doubled). |
| Claim racing an IPO | The claim refuses while `data.ready` is false (`:217`), and `goPublic` sets `ipo.busy` and `data.ready = false` together with no yield in between (`IpoServer.lua:200-201`). An IPO started *during* the claim's save waits on the save lock, and its `after.shares` is computed from `ipo.shares` that already includes the Day 7 Shares (`IpoServer.lua:191`). No Shares are lost either way. |

**F1 (Low): a session whose load failed still shows a claimable reward.** When `load()` fails (`TycoonCore.lua:174-177`), `saved` is nil, the daily section gets defaults and `publish` sets `DailyReady = true` with `DailyBlocked = ""`. The window auto-opens with a live Claim button, and every tap answers `NotLoaded` (`DailyServer.lua:220`). Nothing is granted, so it's safe, but the player is invited to claim something that can never work. *Fix:* in `publish`, set `DailyBlocked = TEXTS.NotLoaded` when `not data.loaded`, and `DailyAutoOpen = false` in that case.

**F2 (Low): a Day 7 claim can consume the day without the Shares.** If `IpoServer.grantShares` returns false (`DailyServer.lua:182-185`) the egg and Cash are already granted and the day is used up; the Shares are only `warn`ed. Today it can only fail for a bad config value (the claim already refuses while `ipo.busy`), so it's a safety-net gap, not a live bug. *Fix:* check `sharesFor(reward) > 0 and IpoServer.isBusy(data)` before step 1, so a refusal happens before anything is granted.
