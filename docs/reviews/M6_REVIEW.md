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

**F2 (Low): a Day 7 claim can consume the day without the Shares.** If `IpoServer.grantShares` returns false (`DailyServer.lua:182-185`) the egg and Cash are already granted and the day is used up; the Shares are only `warn`ed. Today it can only fail for a bad config value (the claim already refuses while `ipo.busy`), so it's a safety-net gap, not a live bug. *Fix:* check `sharesFor(reward) > 0 and IpoServer.isBusy(data)` before step 1, so a refusal happens before anything is granted.

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
