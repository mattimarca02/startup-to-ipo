# Full pre-publish review: security and data integrity

Branch `prepublish-fixes`, code at `778a28e`. All `file:line` references point at that commit. Review only: no `.lua` file, Studio, Roblox place or DataStore was touched. This file lives on `claude/full-review`.

**Read for this review:** CLAUDE.md, ROADMAP.md, CONTRIBUTING.md, docs/PREPUBLISH.md (from `claude/prepublish-checklist`, not committed), docs/PREPUBLISH_RESULTS.md (the copy on `prepublish-fixes`, which is the remote copy plus the fix notes for items 5 and 6), every file in docs/reviews/, and all 20 `.lua` files from top to bottom. Roblox's current documentation was checked for the DataStore limits, ProcessReceipt retries and the Paid Random Items policy (links in section 7 and at the end).

**Not repeated here** (already reviewed and fixed): the M4, M5, M6 and PR #14 findings, the pass purchase retry (`6b3abb2`), the `data.saving` pcall (`ebe59cd`) and the IPO refusal during the pass check (`22c22ff`). Known open items from the M9 list are mentioned only where this review changes their severity.

**How this review differs from the earlier ones.** Those looked at one diff at a time. This one follows a value (Cash, Shares, an employee, an egg, a receipt) through every system and across two servers, the way an exploiter or a server-hopping player would.

`tools/daily_test.py` was not run (no `luau` binary in this session).

## Severity scale

The same scale as the earlier reviews.

| Level | Meaning |
|---|---|
| Critical | A client can cheat, or player data or Robux value is lost or duplicated in a normal situation. |
| High | Normal players will hit it, or it can get the game moderated or broken at launch. Blocks launch. |
| Medium | A real bug in an uncommon situation. Fix before launch if it's cheap, otherwise in the first update. |
| Low | A rare edge case, a confusing message, or a missing safety net. |

Effort: **S** = a few lines in one script, **M** = one script plus tests, **L** = several scripts and a 2-server test.

---

## 1. Save lifecycle across all sections

### What happens to each section, from join to shutdown

| Moment | What the code does | Holds? |
|---|---|---|
| Join | `load` reads the key up to 3 times (`TycoonCore.lua:241-264`), a non-table save counts as a failed read (`:229-235`), a failed read kicks (`:550-556`). Every module sets up its section inside one `pcall` (`:558-591`) and `data.loaded` is set only after all of them (`:598`). | Yes |
| Saving during load | `save()` refuses until `data.loaded` and until all six sections exist (`:327-331`). Autosave, leaving and `BindToClose` all go through it. | Yes |
| Autosave | Every 60 s, one player after another (`:662-669`). | Yes |
| Leaving | `save(player)`, then the plot is freed (`:637-645`). | Yes, but see **FR-1** (a failed save is not retried) and **FR-3** (the plot stays taken while the save runs) |
| `BindToClose` | Saves every player still in `playerData`, one after another (`:671-675`). | Yes at 6 players; see **FR-2** |
| Shutdown during an IPO | The IPO save holds `data.saving`; the leave and shutdown saves wait behind it (`:334-337`). `commitIpo` and `goPublic` finish without yielding after the save returns (`:386-408`, `IpoServer.lua:216-244`), so the waiting saves always write the state after the IPO, or the state before it if the IPO save failed. | Yes |
| Shutdown during a poach | The move's `outgoing` copy stays in the victim's save until the attacker's save is confirmed (`PoachServer.lua:270-287`, `EmployeeServer.lua:396-407`, `:577-579`), and the attacker's `gained` note undoes an unfinished move on the next join (`PoachServer.lua:294-311`). A shutdown that kills the deferred thread leaves both notes on disk. A running negotiation is saved as `refund` (`:774`) and paid back on the next join (`:725-729`). | Yes. But see **FR-4**: the `gained` note can be erased before it does its job |
| Shutdown during a receipt | The receipt and its reward are in memory together, so the shutdown save writes both or neither; Roblox retries if `PurchaseGranted` was not returned. | Yes |
| Shutdown during a daily claim | The reward and `lastClaimDay` change together with no yield (`DailyServer.lua:162-193`); every later save writes both. | Yes |
| Old code saving a new save | Code with the M4 F2 rule keeps unknown top-level sections (`TycoonCore.lua:304-308`, `:566-571`). Code older than that deletes `ipo`, `onboarding` and `daily`. | Only with **Shut down all servers**. See **FR-18** and **FR-19** for the rollback and overlap cases |

### Save size (the 4 MB limit)

Worst case for a fully maxed player, measured on the JSON the server writes:

| Part | Biggest it can get | About |
|---|---|---|
| `team.employees` | 5 base + 3 Extra Desk + 3 Extra Employee Slots = 11, plus `pending` and any `outgoing` still moving | 1.2 KB |
| `team.incubators` | 5 (3 + Extra Incubator x2), plus parked ones | 0.4 KB |
| `shop.receipts` | capped at 100 PurchaseIds (`ShopServer.lua:26`, `:451-457`) | 4 KB |
| `poach.lost` | capped at 50 notes, 30 days (`PoachServer.lua:27-28`, `:751-766`) | 4 KB |
| `poach.losses`, `poach.gained` | pruned to the 10-minute window; one note per unconfirmed move | < 0.5 KB |
| `ipo`, `onboarding`, `daily`, `owned`, `cash`, `lastSeen` | fixed fields, 6 perks, a few goal keys | 0.6 KB |
| **Total** | | **about 11 KB, 0.3% of the 4,194,304-character limit** |

Nothing a client does makes the save grow without a cap: receipts and lost notes are capped, losses are pruned, employees are capped by slots, and unknown keys are only what newer code wrote. **If the limit were ever exceeded**, `SetAsync` would error inside the `pcall` (`TycoonCore.lua:346-355`): every save of that player fails with a warning, and the session behaves like FR-1. No finding: the margin is about 380x.

### FR-1 (Medium): a save that fails is never retried, and the player is never told

**Where:** `TycoonCore.lua:637-645` (leave), `:662-669` (autosave), `:671-675` (`BindToClose`), `:352-356` (a failed save only `warn`s).

**How it breaks:**
1. Roblox DataStore writes fail for a while (an outage, or the server's write budget is used up). Reads still work, so players join normally.
2. Every autosave fails with a warning in the server log only. The player sees nothing.
3. The player leaves. The leave save is tried **once**. It fails.
4. Everything since the last save that worked is gone: if every autosave failed, that is the whole session (Cash, upgrades, hatched employees, an IPO's Shares, HR levels).

Purchases are safe (a failed save returns `NotProcessedYet`, so Roblox retries the receipt on the next join), and the daily claim is safe (the next join shows the day as unclaimed again). Everything else earned in the session is lost.

**Impact:** whole sessions lost during a write outage, with no warning to the player, who keeps playing for nothing. Rare, but it is the most common way Roblox games lose progress, and it is invisible in this game today.

**Smallest fix (S):**
- In the `PlayerRemoving` handler, retry `save(player)` up to 3 times with a 2 s wait while it returns false (the data is still in `playerData` until the handler ends).
- Count failed saves in `data.failedSaves` (reset on success). After 2 failed autosaves in a row, send a toast through `ShopNotify`: "Saving is having trouble. Your progress will be saved when it's back." Tell them again when a save works.

### FR-2 (Low): `BindToClose` saves players one at a time, and saves each one twice

**Where:** `TycoonCore.lua:671-675`, `:637-645`.

**How it breaks:** on shutdown Roblox removes every player, so each `PlayerRemoving` handler saves that player (in parallel), and `BindToClose` then saves every player still in `playerData`, one after another. A player whose leave save is still running is saved a second time after it (the lock makes the second one wait). With 6 players and a healthy DataStore that is a few seconds. With a slow DataStore, the one-by-one loop spends its 30 seconds on the first players and never reaches the last ones; their `PlayerRemoving` save is then the only one, and it gets no retry (FR-1).

**Impact:** at most the last minute of a player's progress, only at shutdown while the DataStore is slow. Grows with players per server (see section 2).

**Smallest fix (S):** in `BindToClose`, start every save with `task.spawn` and wait until all are done (a counter, like `checkPasses` does), and skip players whose leave save already finished. Combine with FR-1's retry.
