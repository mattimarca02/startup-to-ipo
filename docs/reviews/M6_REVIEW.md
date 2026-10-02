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
| Code from before the M4 F2 fix | Would drop the section. Publish M6 with **Shut down all servers** (new section), as for M4 and M5. ROADMAP's M6 status line already says so. |
| `claim()`: "nothing yields between check and set" | **True.** Between `status()` (`DailyServer.lua:151`) and the marker (`:188-191`) the code calls `EmployeeServer.grantEgg` → `freeIncubator`, `startEgg` → `refreshIncubator`, `push` (`FireClient`), then `DailyConfig.cashFor`, `IpoServer.grantShares` → `publish` (`SetAttribute`). None of these wait. The only yield is `core.save` at `:205`, after the marker. A second request during that save sees `now <= lastClaimDay` and is refused. |
| Reward and marker saved apart? | Impossible: both live in the same in-memory state and every save serializes both. If the claim's save fails, the claim still answers success (`:205-209`) and the next autosave or leave save writes both. If *every* save this session fails, both are lost together (nothing doubled). |
| Claim racing an IPO | The claim refuses while `data.ready` is false (`:217`), and `goPublic` sets `ipo.busy` and `data.ready = false` together with no yield in between (`IpoServer.lua:200-201`). An IPO started *during* the claim's save waits on the save lock, and its `after.shares` is computed from `ipo.shares` that already includes the Day 7 Shares (`IpoServer.lua:191`). No Shares are lost either way. |

**F1 (Low): a session whose load failed still shows a claimable reward.** When `load()` fails (`TycoonCore.lua:174-177`), `saved` is nil, the daily section gets defaults and `publish` sets `DailyReady = true` with `DailyBlocked = ""`. The window auto-opens with a live Claim button, and every tap answers `NotLoaded` (`DailyServer.lua:220`). Nothing is granted, so it's safe, but the player is invited to claim something that can never work. *Fix:* in `publish`, set `DailyBlocked = TEXTS.NotLoaded` when `not data.loaded`, and `DailyAutoOpen = false` in that case.

> **Status:** **Fixed** in d5d0029.

**F2 (Low): a Day 7 claim can consume the day without the Shares.** If `IpoServer.grantShares` returns false (`DailyServer.lua:182-185`) the egg and Cash are already granted and the day is used up; the Shares are only `warn`ed. Today it can only fail for a bad config value (the claim already refuses while `ipo.busy`), so it's a safety-net gap, not a live bug. *Fix:* check `sharesFor(reward) > 0 and IpoServer.isBusy(data)` before step 1, so a refusal happens before anything is granted.

> **Status:** **Skipped** (M9 list), commit 85a5ff9.

## 2. Day boundary and time

**Result: no way for a client to claim twice in one server day, and no unfair streak loss found in the code.** The client sends no time; every day number comes from the server's `os.time()` (`DailyServer.lua:45-47`).

| Question | Answer |
|---|---|
| Grace math | `missed = now - last - 1` (`DailyServer.lua:82`). `GraceDays = 1`: claim on D, skip D+1, claim on D+2 → `missed = 1`, place kept (`:83-85`). Skip D+1 and D+2 → `missed = 2`, back to Day 1 (`:87-88`). Matches the window text (`DailyConfig.lua:54`). A player who claims every other day keeps their place forever; that is what `GraceDays = 1` means, so it's a design choice, not a bug. |
| `streak = 0` with `lastClaimDay > 0` (bad data, Debug reset) | Falls to the Day 1 branch with `lostDay = 0` (`:83`, `:87`): no "you missed" line, no crash. |
| Last claim in the future | `now <= last` counts as "claimed today" and never grants (`:79-80`). At join, a value more than 1 day ahead is clamped to today (`:268-272`); exactly 1 day ahead is kept, so the player waits until that day is over (the countdown honestly shows up to 48 h, `:118`). Never a permanent lock-out. |
| Server clock | The only clock trusted is the server's, the same one already trusted for `lastSeen`, egg timers, shields and the IPO cooldown. Two Roblox servers' clocks can differ by a few seconds; see the two-server table in section 3 for what that allows at midnight (net zero). |
| A player in the server across midnight UTC | The 1-second loop republishes for every ready player (`:355-369`), so `DailyReady` flips within a second of the reset and the chip shows CLAIM. The window does not auto-open again (`DailyClient.lua:589-601` returns after one open, and only in the first 60 s), which is the calm behaviour the plan asks for. `claim()` reads the day once (`:150`) and writes that same number (`:188`), so a claim that straddles the second of midnight can't land on two days. |
| Claim at 23:59 and 00:01 UTC | Allowed by design (two different UTC days), as the plan says. Doesn't let anyone get 7 rewards in fewer than 7 server days. |
| Unfair streak loss: egg day with every incubator busy | Refused before anything changes (`:163-170`), the day isn't consumed, and with `GraceDays = 1` even a whole blocked day costs nothing. Only a player who *also* missed the day before loses the place. Acceptable. |

**F3 (Low): `ResetHourUtc` is labelled "safe to change any time", but changing it opens a one-time extra claim.** `DailyConfig.lua:8` says every number below is safe to change; `ResetHourUtc` (`:38`) moves every day number. Moving it *earlier* (e.g. 12 → 0) makes the current hours of the day count as a new day: a player who claimed at 06:00 UTC under the old value can claim again at 07:00. Moving it later just delays the next claim. The config check (`:114-141`) also doesn't check that it's a whole number from 0 to 23. *Fix:* in the header, list `ResetHourUtc` as "decide once before shipping; changing it later lets everyone claim one extra day", and warn in the config check if it's not an integer 0-23.

> **Status:** **Fixed** in a4ae18f (comment only; the config check for a non-integer hour is not added).

## 3. Two servers at once (M4 F10)

**Result: bounded. The save never keeps both servers' rewards; the only real gain needs a reward to leave the save in between, which ROADMAP already records.** There is still no session lock (planned for M9).

| Hop | What happens | Net result |
|---|---|---|
| Claim on A, join B before A's claim save lands | B's `GetAsync` returns the pre-claim save, so B shows Day N as ready and a second claim works there. A's leave save (queued behind A's claim save by the lock) lands; B's later saves (claim save, autosave, leave) overwrite it. | One reward survives (B's). A's reward and A's last seconds of progress are lost. Same streak step either way, so the streak isn't double-advanced. |
| Same, but the player leaves B before A's queued writes land | DataStore's per-key write throttle can delay A's writes by seconds; then A's write is last and wins. | One reward survives (A's). B's is lost. |
| Clocks at midnight: claim on A at 23:59:58 (day D), hop to B whose clock already reads D+1 | B sees `missed = 0`, a new day: claim again. Back on any normal server during D+1: `now <= last`, already claimed. | Two claims seconds apart, but the D+1 claim was just taken early: no extra reward over time. |
| `Shut down all servers` (M6 publish) right after a claim | `BindToClose` saves after the claim save (lock), but the new server may load before that write lands. | Same as the first row: one reward survives. |
| Reward leaves the save before it's overwritten | The only cross-save path is poaching: hatch the daily egg on A, a third player poaches that employee, then B's stale save overwrites A. | One extra employee in the world. This is the existing M4 F10 hole, not new to M6; ROADMAP's M9 list already names it. |

What a hop can *not* do: get two rewards into one save, double-advance the streak, or get Shares twice (Shares never leave the save). The claim's immediate save (`DailyServer.lua:205`) shrinks the window to the length of one `SetAsync`. The plan's statement in section 3 is accurate. No new finding; the session lock in M9 closes it.

## 4. Economy

**Result: no path from daily Cash into the valuation, no way to double daily Shares, and the egg grant respects every limit.**

| Question | Answer |
|---|---|
| Daily Cash → valuation / `addEarnings`? | No. Cash goes to `data.cash.Value` only (`DailyServer.lua:175-178`). The only callers of `addEarnings` are passive income (`TycoonCore.lua:524`), offline earnings (`:490`), Cash packs (`ShopServer.lua:369`) and Studio debug (`IpoServer.lua:385`, `:392`). Nothing listens to `Cash.Changed` on the server. The in-code check (`DailyServer.lua:193-198`) would `warn` if that ever changed. The indirect path (gift Cash buys upgrades, which raise income) is real but intended, and the sim models it (first IPO unchanged). |
| Daily Shares doubled? | No. `grantShares` adds the raw amount (`IpoServer.lua:142-150`); the Shareholder multiplier is only applied in `preview` (`IpoServer.lua:156-159`). `sharesFor` caps the config value at `MaxShares` (`DailyServer.lua:92-98`). An IPO filed right after a claim takes `ipo.shares` (already including the 3) as its base and adds the IPO reward once (`IpoServer.lua:191`). |
| Egg bypasses incubator limits? | No. `grantEgg` uses `freeIncubator`, which only looks at `1..incubatorCount` (base + Extra Incubator perk) (`EmployeeServer.lua:283-290`, `:316-324`). Parked eggs (above the count) live in `team.parked` and are never touched. `hasFreeIncubator` scans the same array, which `refreshCapacity` keeps exactly `incubatorCount` long (`EmployeeServer.lua:618-640`), so the "blocked" label and the real grant agree. |
| Egg bypasses `EggsEnabled`? | Not applicable: `EggsEnabled` only gates Robux items (`ShopConfig.lua:16`, `:179`; `OnboardingConfig.lua:19` says the same for the M5 free egg). Daily eggs are free and not sold. |
| Egg save format | `startEgg` writes `{ egg = key, startedAt, hatchAt }` (`EmployeeServer.lua:296`), the same shape a bought egg has, with the Faster Eggs perk applied. |
| Pass effect on Cash days | `income.Value` includes pass multipliers (`TycoonCore.lua:113`), so a 2x Cash pass doubles Cash days. The plan disclosed this; no Robux item changes whether or what you claim. |

Note, not a finding: Day 6 (30 min of income, free) is worth two-thirds of the `CashMedium` Robux pack (45 min, `ShopConfig.lua:20`). Worth a look when pricing Cash packs, not a bug.

## 5. Studio-only debug handlers

**Result: unreachable on a live server, at four layers.**

1. `addDebugActions()` is only called under `RunService:IsStudio()` (`DailyServer.lua:350-352`).
2. The `ShopDebug` remote is only created under `IsStudio() and ShopConfig.DebugInStudio` (`ShopServer.lua:593-598`). On a live server there is no remote to call.
3. `handleDebug` re-checks both flags and `data.ready` before dispatching (`ShopServer.lua:525-533`, `:565-568`).
4. Each Daily handler re-checks `IsStudio()` (`DailyServer.lua:318`, `:329`).

The client rows (`ShopClient.lua:560-562`) are only built when the remote exists. `DailyNextDay` only moves `lastClaimDay` back, never forward, so no future day is ever saved.

**F4 (Low): Debug changes are saved to the real save.** With Studio API access on, `DailyNextDay` and `DailyReset` change `data.daily`, and the next save writes it to the live DataStore key. A developer who clicks "+1 day" and claims a few times keeps those eggs, Cash and Shares on their real account. Same behaviour as the other debug tools (`GrantProduct`), so it's a convention, not a new hole. *Fix (optional):* note it in the row's description ("saved to your real save").

> **Status:** **Skipped** (M9 list), commit 85a5ff9.

## 6. Client

**Result: display-only, `InvokeServer` is in a `pcall` (`DailyClient.lua:522-533`), no leaking loops** (one 1-second loop for the countdown, `:604-607`; every connection is made once at script start, and the script lives in StarterPlayerScripts, which doesn't re-run on respawn). No DataStore call on the server side of M6 except through `save()`, which is `pcall`ed (`TycoonCore.lua:239-241`). Attribute reads all have defaults (`attr`, `:72-78`). The chip sits vertically inside the valuation bar's height (`:545`), and the M5 goal card sits under the bar (`OnboardingClient.lua:276`), so they can't overlap. The chip hides while a poach panel shows (`DailyClient.lua:474-475`).

`CHIP_ROOM` (54 px) at the sizes the plan names:

| Screen | Layout | Bar (x, width) | Chip (x) | Result |
|---|---|---|---|---|
| 320 x 568 portrait | column | 98, **158** (was 212) | 262-310 | Fits, but see F5 |
| 375 x 667 portrait | column | 98, 213 (was 250) | 317-365 | Fits |
| 667 x 375 landscape | short row | 370, 233 (was 250) | 609-657 | Fits |
| 568 x 320 landscape | short row | **10, 250 on row 2** (was 370, 188 on row 1) | 266-314, y 84 | Fits, but the bar and goal card drop under the HUD row |
| 1920 x 1080 | column | 98, 250 | 354-402 | Fits |

**F5 (Low): the chip's room shrinks the valuation bar and the M5 goal card on the narrowest phones.** On a 320 px portrait screen the bar's minimum width went from 180 to 150 (`IpoClient.lua:247`), so it ends up 158 px wide, and the goal card copies that width (`OnboardingClient.lua:277`). Both use `TextScaled` with an 8 pt minimum, so "Hire 3 employees" and "$1.2K / $1.8K · x1.50 · 📜 12" get small but don't break. On 568 x 320 landscape, `CHIP_ROOM` pushes the bar from the top row to the second row (`IpoClient.lua:233-239`), which moves the goal card down to y = 146 on a 320 px tall screen. *Fix:* check both sizes in **Test → Device** with the goal tracker showing. If the text is too small, put the chip *under* the right end of the bar on screens narrower than about 340 px (the plan's own fallback, open question 4) instead of shrinking the bar.

> **Status:** **Skipped** (Mattia checks the phone layout by hand; M9 list), commit 85a5ff9.

**F6 (Low): IpoClient now waits forever for DailyConfig.** `IpoClient.lua:13` uses `WaitForChild("DailyConfig")` with no timeout. If the new IpoClient is pasted into Studio before `DailyConfig` is added to ReplicatedStorage, the whole IPO HUD and window never build (only an "infinite yield" warning). *Fix:* `WaitForChild("DailyConfig", 10)` with `CHIP_ROOM = 0` and no reminder when it's missing, or say in README's install steps that DailyConfig goes in first.

> **Status:** **Fixed** in 9053170.

**F7 (Low): the chip's poach-panel hook gives up after 30 s.** `DailyClient.lua:563-566` waits 30 s for `PoachWindowGui` and 10 s per panel. On a slow phone that loads PoachClient later, the chip never hides behind the Negotiation or Poach Alert banner for that session. *Fix:* no timeout (it's a `task.spawn` already), or listen to `playerGui.ChildAdded`.

> **Status:** **Skipped** (M9 list), commit 85a5ff9.

## 7. Other findings

**F1 and F2** are in section 1, **F3** in section 2.

**F8 (Low): CLAUDE.md doesn't list M6 yet.** `DailyConfig`, `DailyRemotes`, the `daily` save block and the Daily toast offset (-240) are missing from the project rules file. ROADMAP's M6 status already says this needs Mattia's OK. *Fix:* add them before merging, so the next milestone's Claude sees the section in the save format and doesn't write over it.

> **Status:** **Fixed** in f56cb6a.

Not run here: `tools/daily_test.py` needs the `luau` binary, which isn't installed in this environment. The test file runs the real `DailyServer.lua` and `DailyConfig.lua` with a fake Roblox, which is the right design; Mattia should run it once on the Mac before merging.

## 8. Open PRs #13 and #14 (not reviewed, conflicts only)

A trial merge of each PR into `milestone-6-daily-rewards` conflicts only in **CONTRIBUTING.md** (Ownership rows) and **ROADMAP.md** (status lines). No Lua file conflicts.

- **#13 (IPO Shares growth)** changes only `IpoConfig.sharesFor`. It doesn't touch `IpoServer.grantShares` or the `daily` section, and daily Shares don't go through `sharesFor`, so they stay at 3. But IPOs will pay more Shares, so the plan's "+7% Shares" for the Day 7 reward gets smaller. Re-run `tools/economy_sim.py --daily` after both merge. `docs/ECONOMY.md` and `tools/economy_sim.py` merge cleanly in text, but check that the `--daily` hook still uses the new formula.
- **#14 (security fixes)** changes `IpoServer.lua` in different places (the `core` comment and `goPublic`), not `grantShares`. In `TycoonCore.lua` it retries the load and kicks the player when the load fails; that makes **F1** impossible on live servers. It doesn't touch `save()`, `KNOWN_SECTIONS` or the setup gate, so the `daily` section is unaffected.

## Status after fixes

F1, F3, F6, F8 fixed; F2, F4, F5, F7 skipped and listed in ROADMAP's M9 hardening list. `tools/daily_test.py`: 69 passed, 0 failed (after F1).

## Summary

| Severity | Count | Findings |
|---|---|---|
| Critical | 0 | |
| High | 0 | |
| Medium | 0 | |
| Low | 8 | F1 failed-load session shows a claimable reward · F2 Day 7 Shares granted after the egg · F3 `ResetHourUtc` "safe to change" · F4 debug days saved to the real save · F5 chip room shrinks bar and goal card on 320 px · F6 IpoClient waits forever for DailyConfig · F7 poach-panel hook times out · F8 CLAUDE.md not updated |

**Top 3:** F5 (check 320 x 568 and 568 x 320 in Test → Device with the goal tracker on), F6 (paste DailyConfig before IpoClient, or add a timeout), F3 (`ResetHourUtc` label).

**Verdict: merge,** after the F5 phone check and the CLAUDE.md update (F8). Publish with **Shut down all servers**. The save gate, the claim's no-yield step, the Cash gift rule, the Shares path and the Studio-only debug all hold up in the code. The two-server gap is bounded and already recorded for M9.
