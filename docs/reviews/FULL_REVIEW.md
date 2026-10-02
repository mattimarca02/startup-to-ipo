# Full pre-publish review: security and data integrity

Branch `prepublish-fixes`, code at `778a28e`. All `file:line` references point at that commit. Review only: no `.lua` file, Studio, Roblox place or DataStore was touched. This file lives on `claude/full-review`.

**Read for this review:** CLAUDE.md, ROADMAP.md, CONTRIBUTING.md, docs/PREPUBLISH.md (from `claude/prepublish-checklist`, not committed), docs/PREPUBLISH_RESULTS.md (the copy on `prepublish-fixes`, which is the remote copy plus the fix notes for items 5 and 6), every file in docs/reviews/, and all 20 `.lua` files from top to bottom. Roblox's current documentation was checked for the DataStore limits, ProcessReceipt retries and the Paid Random Items policy (links in section 7 and at the end).

**Not repeated here** (already reviewed and fixed): the M4, M5, M6 and PR #14 findings, the pass purchase retry (`6b3abb2`), the `data.saving` pcall (`ebe59cd`) and the IPO refusal during the pass check (`22c22ff`). Known open items from the M9 list are mentioned only where this review changes their severity.

**How this review differs from the earlier ones.** Those looked at one diff at a time. This one follows a value (Cash, Shares, an employee, an egg, a receipt) through every system and across two servers, the way an exploiter or a server-hopping player would.

`tools/daily_test.py` was not run (no `luau` binary in this session).

## Fix status (round 1, branch `prepublish-fixes`)

| Finding | Status | Commit |
|---|---|---|
| FR-12 odds per creature, exactly 100% | Fixed | `8c1f892` |
| FR-4 poach-chain copy | Fixed | `e813ca7` |
| FR-1 failed saves retried and shown | Fixed | `9605320` |
| FR-5 no session lock | Partly fixed (join re-read); full lock not built | `762b471` |
| FR-13 PolicyService | Fixed (D9 decided: option B, fixed hire order) | `3e42a1b` check, `1afca54` fixed order, `dfe412c` Luck Boost, `ccce737` Eggs tab, `d850a55` restriction changes, `94e30cf` tests (options: `7f55d13`) |
| FR-15 Max Players 6 | Documented; set it by hand | `ef8edfa` (docs/PUBLISH_RULES.md) |
| FR-18 rollback floor | Fixed (docs) | `ef8edfa`, A10 rule `387b3d0` |
| FR-19 hard shutdown only | Fixed (docs) | `ef8edfa` |
| FR-2, FR-3, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-14, FR-16, FR-17 | Skipped (Low, first update or C6/C8) | |

`tools/daily_test.py` after the fixes: 287 passed, 0 failed (the 175 earlier checks plus 112 new: odds 70, poach move 16, leave save 13, join re-read 13).

Studio scripts to sync: TycoonCore, ShopServer, PoachServer (ServerScriptService); CreatureConfig, ShopConfig, IpoConfig (ReplicatedStorage); EmployeeClient, DailyClient, ShopClient (StarterPlayerScripts).

Round 2 (FR-13, option B): `tools/daily_test.py` 462 passed, 0 failed (the 287 above plus 175 new: fixed order 103, fixed hires and save section 36, policy check 29, save payload 7). Studio scripts to sync: TycoonCore, ShopServer, EmployeeServer (ServerScriptService); CreatureConfig, ShopConfig (ReplicatedStorage); ShopClient, EmployeeClient (StarterPlayerScripts). New save section `fixedHires`: publish with **Shut down all servers**.

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

> **Status:** **Fixed** in `9605320`: the leave save is retried (3 tries, 2 s then 4 s), and after 2 failed saves in a row the player is told, then told again when saving works. The BindToClose part is FR-2 (skipped).

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

> **Status:** **Skipped** (Low, first update).

**Where:** `TycoonCore.lua:671-675`, `:637-645`.

**How it breaks:** on shutdown Roblox removes every player, so each `PlayerRemoving` handler saves that player (in parallel), and `BindToClose` then saves every player still in `playerData`, one after another. A player whose leave save is still running is saved a second time after it (the lock makes the second one wait). With 6 players and a healthy DataStore that is a few seconds. With a slow DataStore, the one-by-one loop spends its 30 seconds on the first players and never reaches the last ones; their `PlayerRemoving` save is then the only one, and it gets no retry (FR-1).

**Impact:** at most the last minute of a player's progress, only at shutdown while the DataStore is slow. Grows with players per server (see section 2).

**Smallest fix (S):** in `BindToClose`, start every save with `task.spawn` and wait until all are done (a counter, like `checkPasses` does), and skip players whose leave save already finished. Combine with FR-1's retry.

---

## 2. DataStore budget and throttling

### The limits (Roblox docs, checked 2026-10-02)

- Server budget per minute, standard DataStores: **reads 60 + 40 x players, writes 60 + 40 x players**. (Older docs said 10 x players; the earlier reviews' numbers are out of date and too pessimistic.)
- Per key: 25 MB read and 4 MB written per minute. There is no documented fixed cooldown between two writes to the same key any more; a key that is written too fast gets `KeyThrottled`.
- Each request type has a throttle queue of 30 requests. When it's full, requests fail with errors 301-306.
- One value: 4,194,304 characters.

### Every DataStore call in the game

There are only three: `GetAsync` in `load` (`TycoonCore.lua:250`) and `peekSave` (`:272`), and `SetAsync` in `save` (`:349`). No `UpdateAsync`, no OrderedDataStore, no MemoryStore, no MessagingService. Every call is in a `pcall`. Nothing checks `GetRequestBudgetForRequestType` (PR14 F7, still open).

| Caller | Request | How often |
|---|---|---|
| Join (`load`) | 1 read, up to 3 on failure | once per join |
| `reconcile` on join (`PoachServer.lua:294-311`) | 1 read per open `gained` note | almost always 0 |
| Autosave | 1 write per player | every 60 s |
| Leave | 1 write | once |
| `BindToClose` | 1 write per player still loaded | at shutdown (doubles the leave write, FR-2) |
| Receipt (`ShopServer.lua:476`) | 1 write | per purchase, and per retry |
| Perk bought (`IpoServer.lua:263`) | 1 write | at most 24 ever (all perk levels) |
| HR level (`PoachServer.lua:630`) | 1 write | at most 5 ever |
| Poach: failed roll (`:405`) | 1 write | at most once per 30 s cooldown |
| Poach: move (`confirmSave`, `:202-217`) | 2 writes (attacker, then victim); a read instead of a write for a player who left; up to 5 tries each | per successful poach or Counter-Offer |
| Daily claim (`DailyServer.lua:207`) | 1 write | once per day |
| IPO (`commitIpo`) | 1 write | at most once per 60 s cooldown |

### Load at 6, 20, 50 and 100 players per server

| Players | Budget (reads / writes per min) | Steady use | Busy peak (everyone buying, poaching, joining) | Margin |
|---|---|---|---|---|
| 6 (the real maximum: 6 plots) | 300 / 300 | about 6 writes, ~1 read | ~25 writes, ~10 reads | > 10x |
| 20 | 860 / 860 | 20 writes | ~80 writes | > 10x |
| 50 | 2,060 / 2,060 | 50 writes | ~200 writes | > 10x |
| 100 | 4,060 / 4,060 | 100 writes | ~400 writes | > 10x |

Use grows at the same rate as the budget, so the budget is never the bottleneck. A client cannot make the server save without paying for it: every save path above needs Cash, Shares, Robux, a cooldown or a once-a-day check.

The game can't actually have more than 6 loaded players (`MAX_PLOTS = 6`, `TycoonCore.lua:62`); the 7th is kicked. The 20/50/100 rows only matter if the plot count is raised later. Then the real limits are not the budget but the one-by-one loops: autosave (`:665-667`) and `BindToClose` (FR-2). At 100 players, 100 saves of about 0.3 s each take 30 s, which is the whole `BindToClose` window. Server size vs plots is **FR-15** (section 8).

### During a DataStore outage or a full throttle queue

| Path | What happens | OK? |
|---|---|---|
| Join | 3 reads, waiting 2 s then 4 s, then a kick with "please rejoin" (`TycoonCore.lua:241-264`, `:550-556`). Nothing is saved. | Yes |
| Leave, autosave, `BindToClose` | A warning; the progress is lost (FR-1). | No: FR-1 |
| Receipt | `NotProcessedYet`; Roblox retries on the next join or purchase. The reward stays in memory with its PurchaseId, so the retry can't pay twice. | Yes |
| IPO | "The IPO couldn't be saved. Nothing changed." | Yes |
| Daily claim | Granted in memory, answer says `saved = false`; the next save writes both. If no save works, both are lost together. | Yes |
| Poach move | `confirmSave` retries 5 times over ~30 s, keeping the employee `inTransit` (it blocks that player's IPO meanwhile). On failure the `gained` note stays for the next join. | Yes |
| `reconcile` | A failed read keeps the note for next time (`PoachServer.lua:297-298`). | Yes |

### Can a DataStore call block a join or a leave?

- **A join waits for:** `load` (up to 3 reads plus 6 s of waits; each read can itself sit in the throttle queue), the pass check (at most 10 s, `ShopServer.lua:388-395`), and one `peekSave` per open `gained` note (no time limit). Each join runs in its own thread, so one slow join never holds up another player's join. The player stands on an empty plot meanwhile, and every window answers "Still loading".
- **A leave waits for:** the leave save, which waits for any save already running (`TycoonCore.lua:334-336`, no time limit). The player is already gone, but their **plot stays taken** until the save returns. That is **FR-3**.

### FR-3 (Low): a slow leave save keeps the plot taken, so the next player is kicked with "This server is full"

> **Status:** **Skipped** (Low, first update). Matters more now that Max Players must be 6.

**Where:** `TycoonCore.lua:637-645` (the plot is freed only after `save` returns), `:509-518` (no free plot = kick right away).

**How it breaks:**
1. A 6-player server is full. Player A leaves. Roblox sees 5 players and sends a new player B at once.
2. A's leave save is still running (slow DataStore, or it is waiting behind A's own receipt or poach save). `plotOwners[A's slot]` is still set.
3. B's `onPlayerAdded` finds no free plot and kicks B: "This server is full, please join another one."

**Impact:** a joiner is bounced. More likely once the server size is set to exactly 6 (FR-15), and during DataStore trouble. No data is lost.

**Smallest fix (S):** in `onPlayerAdded`, when no slot is free, wait up to 10 s (checking every 0.5 s while the player is still in the game) before kicking.

---

## 3. Session locking (F10), concretely

### Why a hop can only *move* value, not copy it, except through poaching

Every save is a full `SetAsync` of the whole player (`TycoonCore.lua:349`), so the save on disk is always one server's complete picture. When two servers hold the same player, the last write wins and the other server's changes vanish. That's why hopping undoes things but can't add a second copy of anything that lives only in that one save (Cash, Shares, perks, eggs, IPO count, streak).

A copy needs a value that lives **outside** the player's own save. In this game there are only two:
- **another player's save**, reached through poaching and the Counter-Offer (`PoachServer.transfer`);
- **Roblox's receipt state**: a receipt answered `PurchaseGranted` is never sent again.

### Hop steps, asset by asset

"Two devices" means: the player is in server A on device 1 and joins server B on device 2. Roblox kicks device 1, but server B reads the save before A's leave save lands.

| Asset | Exact steps | Result | How easy |
|---|---|---|---|
| **Cash** | 1. In A, spend Cash (HR level, failed poach, egg). 2. Within ~1 s, before A's save of that spend lands, join B. 3. Play on in B. | The spend is undone, and so is everything else since A's last landed save. No Cash is created. | Hard (two devices, sub-second timing). Gain: an undo. |
| **Shares, perks, IPO** | Same, right after buying a perk (saved at once, `IpoServer.lua:263`) or going public. Then go public or buy again in B. | One IPO or one purchase survives (B's). Shares are never doubled: the M4 F10 case. | Hard. No gain. |
| **Employees** | **No hop needed:** FR-4 below (3 accounts). With a hop, the poached victim keeps the employee for the attacker's session only (`reconcile` takes it back on the attacker's next join). | **Permanent copy** (FR-4). | Easy with a script, luck by hand. |
| **Eggs (free egg, M5 F8)** | New player: join A (free egg), join B within ~1 s of A's first save. | B gives the egg again; one save survives, so one egg. | Hard. No gain. |
| **Daily streak and reward (M6 F10)** | Claim in A; device 2 joins B before A's claim save lands; claim again in B. | One reward survives. A copy survives only if the egg hatched in A and that employee was poached by an alt in A before B's save overwrote it. | Medium (two devices). Gain: one egg's employee to an alt per day. |
| **Purchase grant** | Buy in A while device 2 is already loading B. | **Never duplicated** (the receipt isn't sent again). Can be **lost**: FR-5. | Accidental only. |

### FR-4 (Medium): an employee can be copied through a poach chain, no server hop needed

> **Status:** **Fixed** in `e813ca7`: `movable()` refuses to move an employee whose holder has an open `gained` note, except back to where the note says it came from (the owner's Counter-Offer). Used in `start`, `finish`, `counterOffer` and the Poach window; 16 checks.

**Where:** `PoachServer.lua:266-268` (a new move erases the old holder's `gained` note), `:270-287` (when the victim's save can't be confirmed, the attacker keeps the note but the employee becomes poachable again), `:452-454` and `:489-490` (only `inTransit` blocks a move).

**How it's exploited** (3 accounts in one server: V, A and C; V owns an Epic employee X; V has HR level 0 and no shield):
1. A poaches X from V. On success, `transfer` puts X on A's team with a `gained` note `{ from = V }`, keeps X in V's save as `outgoing`, and starts saving A (`:270-271`).
2. V leaves **before A's save returns** (an exploit script can call `LocalPlayer:Kick()` when the `Poached` event arrives, about 0.1-0.5 s; A can widen the window by buying an HR level just before, so A's confirm save waits behind that save). V's leave save still contains X (`outgoing` is saved as an employee, `EmployeeServer.lua:577-579`).
3. A's save lands. V is gone, so `finishRelease` and V's `lost` note are skipped (`:272-279`). `confirmSave(V, X, false)` reads V's save, finds X, returns false (`:209-212`). A keeps the `gained` note, and `inTransit[X]` is cleared (`:286`). So far this is the design: on A's next join, `reconcile` would hand X back.
4. Before A leaves, C poaches X from A (A has no shield: A wasn't poached). The new `transfer(A, C)` sets `A.gained[X] = nil` (`:268`). The note that would have undone step 1 is gone.
5. C's and A's saves confirm normally. **Final: V's save has X, C's save has X.** A's refund for step 1 is gone too. On C's next join, `reconcile` checks A's save: no X, and A's `lost` note says C took it, so C keeps it.

**Impact:** a permanent copy of any poachable employee (Common to Epic; Legendary can't be poached). Costs two poach fees and two lucky rolls (30-40% for an Epic). Value is limited (no trading, slots are capped), but it is a true duplication, and alt farms are cheap.

**Smallest fix (S):** an employee whose holder still has an open `gained` note can't be moved on. In `start` (`:454`) and `counterOffer` (`:490`), refuse with "That employee isn't available" when `poachOf(target).gained[employeeId]` (or the attacker's, for the Counter-Offer) is set, and hide it in `targetsFor` (`:529`) the same way as `inTransit`. The note is cleared once the victim's save confirms, so normal moves are not affected. Add a `daily_test.py`-style check if possible.

### FR-5 (Medium): no session lock: an overlapping session can wipe a paid purchase, and a fast reconnect loses up to a minute

> **Status:** **Partly fixed** in `762b471` (the interim): a save less than 75 s old is read again after 7 s before setup. The full session lock is **not built** (by request).

**Where:** `TycoonCore.lua:241-264` (load reads without any lock), `:325-357` (blind `SetAsync`), `ShopServer.lua:461-480`.

**How it breaks (purchase):**
1. Device 1 is in server A. Device 2 joins server B; B reads the save (without the purchase below).
2. Before Roblox kicks device 1, the player buys a Cash pack (or Instant Hatch, Poach Shield) on device 1. A grants it, saves, answers `PurchaseGranted`.
3. B never sees the purchase. B's autosave overwrites A's save. Roblox won't send the receipt again.

**How it breaks (no exploit, normal players):** the client loses its connection; the player taps Reconnect and lands in a new server while the old server still holds them (it takes a while to notice). The new server reads the last autosave (up to 60 s old). The old server's leave save lands later and is then overwritten by the new server's autosave. Up to 60 s of progress is lost. If the old server's write is stuck in a throttle queue and lands *after* the new session's last save, the whole new session is lost.

**Impact:** paid and not received (rare, two devices at once); "I lost my last minute" after reconnects (common enough to cause reviews); the M4 F10 / M5 F8 / M6 F10 hops above.

**Smallest fix:** the lock below (M). If it can't make launch, an interim (S): on join, if `os.time() - saved.lastSeen < 75` (the save may come from a session that is still running), wait 7 s and read again before setting up. It costs every quick rejoin 7 s of loading but removes most reconnect losses. It does not stop the two-device purchase case.

### FR-6 (Low): an attacker who hops at the exact moment of a poach can destroy the victim's employee

> **Status:** **Skipped** (Low; closed by the full lock).

**Where:** `PoachServer.lua:202-217`, `:294-311`, `TycoonCore.lua:241-264`.

**How it breaks:** A's poach succeeds in server 1; device 2 has server B read A's save **before** A's confirm save lands (a sub-second window). Server 1 then confirms A (reading A's leave save, which has X), releases X from V for good and saves V. B's later saves overwrite A's save without X. Nobody has X. If A's last autosave happened during the 8-10 s negotiation, B also paid the fee back from that save's `refund` (`PoachServer.lua:725-729`), so A paid nothing.

**Impact:** griefing one employee; needs two devices and sub-second luck. Closed by the lock. **Fix:** the lock below; nothing separate.

### The smallest lock that fits the current save format

1. **Where it's stored:** a new top-level section `session = { id, at }` (`id` = `game.JobId`, or a GUID in Studio where `JobId` is empty; `at` = `os.time()`). Add `session` to `KNOWN_SECTIONS` (`TycoonCore.lua:70`) so this code never treats it as unknown. Code with the F2 rule (M4 and later) keeps it as an unknown section and writes it back unchanged, which only makes the lock look held a little longer; code from before F2 drops it, which only frees it. No other section changes, so old saves keep loading.
2. **Taking it, in `load`:** replace `GetAsync` with `UpdateAsync`. In the callback: if the stored `session` belongs to another server and is younger than 90 s, return `nil` (write nothing) and let `load` try again every 3 s for up to 15 s. Otherwise set `session = { id = ours, at = now }` and return the save. After 15 s, take it anyway (Roblox has already kicked the other device, and a crashed server's lock is stale). A read error keeps today's path: 3 tries, then the load-failure kick (`:550-556`).
3. **Keeping it, in `save`:** build the payload exactly as today (outside the callback; `buildPayload` doesn't yield), then `UpdateAsync` with a callback that returns `nil` if the stored `session.id` isn't ours, else the payload with `session = { id, at = now }`. If the lock was taken by another server: set `data.loaded = false` (this session never saves again, the same flag the load gate uses) and kick with "You joined another server". The 60 s autosave refreshes `at`, so a live session never looks stale.
4. **Releasing it:** the leave save writes `session = nil`. `BindToClose` does the same.
5. **What stays the same:** the all-modules-loaded gate (`data.loaded` is still set only at `:598`), the kick on load failure, `peekSave` (read-only `GetAsync`, never touches `session`), `commitIpo`'s transform (it runs before the callback, inside `buildPayload`), and the one-save-at-a-time lock.
6. **Cost:** one `UpdateAsync` per save instead of a `SetAsync`; still a small fraction of the budget in section 2.
7. **Tests:** two Studio servers with negative-ID players: join A, join B (B waits, then takes over, A's next save stops and kicks); kill A mid-session (B waits at most 15 s); IPO and poach during the takeover.

Effort **M** (TycoonCore plus `daily_test.py` cases), plus a 2-server test. It closes FR-5, FR-6, M4 F10, M5 F8 and M6 F10. It does **not** close FR-4, which needs no hop.

---

## 4. Purchases and receipts

### ProcessReceipt, product by product

All six products go through one path: `processReceipt` (`ShopServer.lua:482-498`) -> `grantProduct` (`:461-480`) -> `applyProduct` (`:426-449`).

| Product | Effect applied | Where |
|---|---|---|
| Pile / Bag / Vault of Cash | `max(minCash, income x 60 x minutes)` to Cash, and `addEarnings` (raises the valuation, on purpose) | `:434-439`, `ShopConfig.lua:188-191` |
| Luck Boost | `luckUntil = max(luckUntil, now) + 15 min` | `:440-443` |
| Instant Hatch | `instantHatches += 1` | `:444-447` |
| Poach Shield | PoachServer's handler: `shieldUntil = max(shieldUntil, now) + 60 min`, and calls off a deal against the buyer | `PoachServer.lua:865-874` |

| Question | Answer | Holds? |
|---|---|---|
| Idempotent by PurchaseId? | `receiptSet` is checked, the reward applied and the PurchaseId remembered with **no yield in between** (`:468-473`). The list is saved in `shop.receipts` (last 100) and reloaded into `receiptSet` on join (`:357-360`). | Yes |
| Granted only after the save? | `PurchaseGranted` only when `core.save` returns true (`:476-479`). The reward and the PurchaseId are always in the same payload. | Yes |
| Save not loaded | `not data.loaded` returns `NotProcessedYet` (`:463-465`). On live servers a failed load kicks, so this is Studio only. | Yes |
| Player not in the server | `GetPlayerByUserId` is nil: `NotProcessedYet` (`:488-491`); Roblox retries on their next join. | Yes |
| Player leaves during the 30 s wait | `waitForData` returns nil: `NotProcessedYet`. | Yes |
| Player leaves after the reward was applied | Either the leave save already contains the reward and the PurchaseId (then the retry finds the PurchaseId and only saves), or it was built before the reward (then the receipt's own save finds `playerData` cleared, answers `NotProcessedYet`, and the next join grants it once). | Yes, both orders |
| The grant throws | `pcall` -> `NotProcessedYet` (`:492-496`). Nothing in `applyProduct` can throw today; if a future handler threw halfway, its half-applied part could be given again on the retry. | Yes today |
| Two receipts at once | Each applies without yielding, then the saves queue on `data.saving`. Same PurchaseId twice: the second sees `receiptSet`. | Yes |
| During an IPO save | `data.ready` is false, so the receipt waits (up to 30 s) and lands after the reset. A Cash pack bought just *before* going public is wiped with the rest of the Cash; the confirm screen shows the live Cash amount (`IpoClient.lua:636-681`). | Yes |
| Debug grants | Only through `ShopDebug`, which exists only in Studio (`:661-666`, `:591-595`). | Yes |

### Game passes

| Path | What happens | Holds? |
|---|---|---|
| Join | All passes asked at once; loading waits at most 10 s, then each pass applies as soon as Roblox answers (`:262-287`, `:375-396`). IPO refused while the check runs (`IpoServer.lua:169-173`, `:191-193`). | Yes |
| Bought in game | Granted only when `UserOwnsGamePassAsync` says yes, retried every 5 s for 120 s (`:293-324`). | Yes |
| Bought on the website | The 120 s recheck loop picks it up (`:702-712`). | Yes |
| A faked "purchase finished" event | If an exploit can make Roblox fire `PromptGamePassPurchaseFinished` for itself, the server still asks Roblox before granting. At most one confirm loop per pass per player (`:299-300`), so at most 6 loops of ~24 calls each per 2 minutes, and the only effect is a misleading toast on the exploiter's own screen. | Yes |
| Pass refunded or revoked by Roblox | Passes are never saved: the next join asks Roblox again, so a revoked pass is gone after a rejoin. Developer products have no revoke callback; Roblox handles the Robux side. | Yes (nothing to do) |
| Join check times out | Offline earnings are paid without the 2x / VIP multiplier and not topped up later (M4 re-review low 1, still open). | Known |

**Can a player pay and receive nothing?** Only through FR-5 (an overlapping session), FR-7 (an item on sale that ShopConfig doesn't know) and FR-8 (a receipt that waits longer than 30 s). **Can a player receive twice?** No path found: a reward is never saved without its PurchaseId, and a PurchaseId is never dropped while its receipt can still be retried (the 100-receipt cap only drops IDs that were already granted).

### FR-7 (Low): a developer product that is on sale but missing from ShopConfig charges the player and gives nothing for up to 3 days

> **Status:** **Skipped** (Low): run `sync_monetization.py --dry-run` before launch (checklist C6).

**Where:** `ShopServer.lua:483-487`, `ShopConfig.lua:176-179`.

**How it breaks:** any product on sale in the universe whose ID isn't in `ShopConfig.Products` (an old test product, the skipped `3715692115` if it still exists and is on sale, a product created in Creator Hub but not synced) answers `NotProcessedYet` forever with only a server warning. Roblox keeps retrying and refunds the Robux after about 3 days (DevForum; the API docs don't state it). Players reach such a product only through a prompt the game doesn't show, so today this needs a stray prompt (another game's or a Roblox page linking it).

**Impact:** a confused paying player and a support request. No Robux kept.

**Smallest fix (S):** before launch, run `sync_monetization.py --dry-run` (checklist C6) and take every product that isn't in ShopConfig off sale. Optional: in `processReceipt`, `notify` the player "This item isn't sold here anymore; Roblox will refund it" for an unknown product.

### FR-8 (Low): a receipt that waits more than 30 s is not retried until the player rejoins, and nobody tells them

> **Status:** **Skipped** (Low, first update).

**Where:** `ShopServer.lua:27` (`DATA_WAIT_SECONDS = 30`), `:413-423`, `:462-465`.

**How it breaks:** the player buys right after joining while the join is slow (3 load tries with 6 s of waits, the 10 s pass check, a `reconcile` read during DataStore trouble), or during an IPO save stuck in the throttle queue. After 30 s the receipt answers `NotProcessedYet`. Roblox retries only on the player's next join or next purchase. The purchase dialog said "success" and the game shows nothing.

**Impact:** a paying player waits until they rejoin (or loses the purchase to Roblox's ~3-day refund if they never come back). Rare: needs a slow join or a slow IPO save.

**Smallest fix (S):** raise `DATA_WAIT_SECONDS` to 90, and when answering `NotProcessedYet` while the player is still in the server, `notify` them: "Your purchase will arrive when your game finishes loading. If it doesn't, rejoin."

---

## 5. End-to-end economy exploits

### Where Cash, valuation and Shares come from

| Value | Sources | Raises the valuation? |
|---|---|---|
| Cash | income tick (`TycoonCore.lua:648-659`), offline (`:608-617`), Cash packs (`ShopServer.lua:434-439`), daily Cash days (`DailyServer.lua:177-180`), poach refund (`PoachServer.lua:325`, `:727`, `:305`), Counter-Offer payment to the poacher (`:276-278`) | Only income, offline and Cash packs (`addEarnings`). Gifts, refunds and payments add to Cash directly. Correct. |
| Shares | IPO (`IpoServer.lua:202-205`), Day 7 (+3, `DailyServer.lua:183-187`, never doubled) | n/a |
| Spends | green pad, eggs, poach fee, Counter-Offer, HR pad, perks | Every spend checks the balance first, on the server (`TycoonCore.lua:177`, `EmployeeServer.lua:316`, `PoachServer.lua:461`, `:492`, `:622`, `IpoServer.lua:257`). No remote carries an amount. |

### Combinations checked

| Combination | Result |
|---|---|
| IPO + poach | A deal against you is called off and refunded once, after the IPO save (PR #14). Your own deal or an employee in transit blocks the IPO. Nothing is created. |
| IPO + Counter-Offer | The victim's open offer is dropped on IPO; a Counter-Offer against a player whose IPO is saving waits (`PoachServer.lua:486-488`). |
| IPO + daily | Claims are refused during the IPO save; Day 7 Shares claimed before an IPO are part of the IPO's base, not added twice (`IpoServer.lua:205`). Daily Cash claimed right before an IPO is reset with the rest (the confirm screen says so). |
| IPO + onboarding egg | `seenIntro` survives the IPO; a post-IPO save also has `ipo.count > 0`, so `hasProgress` is true anyway. No second egg. |
| IPO + offline income | Offline Cash raises the valuation, so a player can return and go public at once. Shares are capped at 2x IPO-ready (`IpoConfig.lua:42`, `:161`), so long absences buy nothing extra. Intended. |
| IPO + Cash packs | Robux raises the valuation and so the Shares, up to the same 2x cap. Intended (`ShopServer.lua:437`). |
| IPO + Instant Hatch / Poach Shield / Luck Boost | All kept through the IPO (`shop` and `poach` aren't reset). A token is used only when it skips a real timer (`EmployeeServer.lua:339-345`). |
| IPO + perks | Perks are bought with no yield between the check and the spend (`IpoServer.lua:249-265`); two quick buys each see the new balance. |
| Poach + Counter-Offer between alts | The Counter-Offer price is 50% of the fee and goes to the poacher; the fee itself is a sink. Moving Cash between alts this way always loses Cash. |
| Poach chain | **FR-4** (copies an employee). |
| Offline income + rejoin loops | Online pays 100%, offline 50%, capped at 8 h (+2 h per Night Shift level). `lastSeen` is written on every save, so each join pays only for the time since the last save. A rejoin loop earns less than staying. |
| Free egg / daily / new-player shield + rejoin | Each is gated by saved state (`seenIntro`, `lastClaimDay`, `saved == nil`), so rejoining gives nothing. Hops: section 3. |
| Alt accounts as farms | An alt can collect the free egg and 7 days of daily eggs and let a main poach the result (after the 15-minute new-player shield; Legendaries can't be poached). This is the cost of player-to-player moves, not a bug. Worth watching in analytics. |
| Clock changes | Only the server's `os.time()` is used (eggs, shields, cooldowns, daily, offline). The client sends no time. Servers differ by seconds; the M6 review showed the midnight case nets zero. |

### Overflow and precision (2^53)

- Cash and Income are `IntValue`s (64-bit integers). A maxed player earns about (183 from upgrades + 11 x 175 from Legendaries) x 3 (2x Cash and VIP) x 5.7 (the multiplier at IPO 20) = about 36,000 Cash/s. A year of non-stop play is about 1.1e12, 8,000 times below 2^53 (9.0e15).
- The IPO threshold `81,000 x 2.5^n` passes 2^53 at IPO 28. Reaching IPO 20 alone needs a 7.4e12 valuation, about 6.5 years of non-stop play at the rate above. Not reachable.
- Shares are small whole numbers. `formatCash` would print `$1e+15` above 1e15: cosmetic and unreachable.

**No duplication or inflation of Cash, Shares or valuation was found** apart from FR-4 (an employee) and the bounded hops in section 3.

### FR-9 (Low): several saved numbers still accept infinity, which turns into permanent Luck Boost, tokens, shields or Cash

> **Status:** **Skipped** (Low, first update, together with PR14 R8).

**Where:** `ShopServer.lua:351-356` (`luckLeft`, `instantHatches`: NaN is checked, infinity isn't), `PoachServer.lua:704-705` (`shieldLeft`, `cooldownUntil`), `:721` and `:725-729` (`gained` refund, `refund`), `IpoServer.lua:350-353` (PR14 R8).

**How it breaks:** a save with `luckLeft = inf` gives Luck Boost forever; `instantHatches = inf` gives endless Instant Hatches; `shieldLeft = inf` makes a player unpoachable forever; a huge `refund` becomes Cash; `ipo.count = inf` blocks every IPO (R8). Only the server writes saves and DataStore JSON can't carry infinity, so this needs a save edited by a tool or a future bug.

**Impact:** none today; it's the same class as PR14 R8, which was left Low. Listed so all of them are fixed together rather than one at a time.

**Smallest fix (S):** one rule everywhere a saved number is read: `tonumber`, then reject NaN, `math.huge`, `-math.huge` and negatives, then clamp to a sane maximum (for example 1e15 for Cash amounts, 30 days for timers), with a `warn`. Each module can carry a 5-line `finiteNumber(value, max)` helper.

---

## 6. Remotes and client trust

### Every entry point a client can reach

There is **no `OnServerEvent` anywhere**: all six RemoteEvents (`ShopNotify`, `TeamUpdate`, `EggHatched`, `PoachEvent`, `IpoEvent`, `OnboardingNotify`) are server-to-client only. A client firing one reaches no code; Roblox queues and then drops the calls with a warning. The client-to-server surface is five RemoteFunctions (plus `ShopDebug`, which only exists in Studio), four `Touched` pads, the incubator `ProximityPrompt`s, and the purchase events Roblox fires.

| Entry | Arguments checked | Spam cost on the server | Holds? |
|---|---|---|---|
| `TeamAction` (`EmployeeServer.lua:444-469`) | `action` string; `Hatch`/`InstantHatch` index is a whole number 1..incubators (NaN and inf fail `% 1`); `BuyEgg` key looked up in config; `Fire`/`ResolvePending` string looked up in the team | `Sync` builds a snapshot and fires it back on every call; the rest are lookups | Yes |
| `PoachAction` (`PoachServer.lua:562-581`) | `Targets` limited to one per 0.25 s; `Start` needs a number and a string of at most 64; `CounterOffer` no argument | `Targets` builds every player's employee list (bounded by the limit) | Yes |
| `IpoAction` (`IpoServer.lua:267-287`) | `GoPublic` number must equal `count + 1`; `BuyPerk` key in config | `Preview` counts eggs | Yes |
| `OnboardingAction` (`OnboardingServer.lua:199-211`) | only `DismissTracker` | none | Yes |
| `DailyAction` (`DailyServer.lua:214-231`) | only `Claim`, 1 s debounce | none | Yes |
| Green, HR and IPO pads | the touching character must be the plot owner; Cash checked; HR has a 2 s cooldown, IPO pad 3 s | Exploiters can touch from far away, which only saves them walking | Yes |
| Incubator prompts | `who == player and data.ready` (`EmployeeServer.lua:501-505`) | none | Yes |
| VIP door | prompts the VIP pass at most every 10 s per player | none | Yes |
| `PromptGamePassPurchaseFinished` | never trusted, ownership asked from Roblox (section 4) | bounded | Yes |
| Player attributes | the server writes them and never reads them back (only `Home` on server-owned models) | n/a | Yes |

**Values taken from the client:** only action names, an incubator index, an egg or perk key, an employee ID, a target UserId and the IPO number. No amount, price, time, chance or result. No table argument is ever walked, so a deep or huge table costs only Roblox's own decoding (capped by its remote size limit).

**Still open from PREPUBLISH_RESULTS item 7 (not new):** string arguments other than `Start`'s have no length cap, and only `Targets` and `Claim` are rate-limited. A spammed `Sync` costs a snapshot plus a message back to the spammer. In a 6-player server this can't hurt others noticeably; a 20 calls/s per-player cap in each `onAction` would remove the question (S).

### Per-player state and memory

| Module | Tables keyed by player or ID | Cleaned on leave? |
|---|---|---|
| TycoonCore | `playerData`, `plotOwners` | Yes, after the leave save (`:637-645`) |
| ShopServer | `lastDebugReceipt`, `doorCooldown`, `passCheckPending`, `passConfirming` | Yes (`:680-685`), but see FR-10 |
| PoachServer | `negotiations` (cancelled on leave), `lastTargetsCall` (cleared), `inTransit` (cleared when the move's saves finish, within ~60 s) | Yes |
| EmployeeServer, IpoServer, OnboardingServer, DailyServer | nothing per player outside `playerData` | n/a |

A player who leaves **during** setup (while `ShopServer.setupPlayer` waits for the pass check, or `reconcile` reads another save) lets the remaining `setupPlayer` calls run for a player who is gone: they build pads and incubators into the already destroyed plot folder, and the `pcall` result is then ignored (`TycoonCore.lua:592`). Nothing is stored in a module table, so it's garbage collected. Not a finding.

### FR-10 (Low): `passConfirming` is re-created for a player who already left, and never removed

> **Status:** **Skipped** (Low).

**Where:** `ShopServer.lua:289`, `:294-298`, `:680-685`.

**How it breaks:** `PromptGamePassPurchaseFinished` arrives while the player is leaving: ShopServer's `PlayerRemoving` already cleared `passConfirming[player]`, but TycoonCore hasn't removed their data yet (its leave save is still running), so `getShop` still works and `confirmPurchasedPass` creates `passConfirming[player] = {}` again. The loop ends at once (`player.Parent` is nil), leaving an empty table that holds the Player object forever.

**Impact:** a few hundred bytes per occurrence, only when a pass purchase finishes during a leave. Harmless in practice.

**Smallest fix (S):** at the end of `confirmPurchasedPass`, `if next(confirming) == nil then passConfirming[player] = nil end`.

### FR-11 (Low): the in-server leaderboard puts display names into rich text without escaping them

> **Status:** **Skipped** (Low).

**Where:** `IpoClient.lua:770` (the row label has `RichText = true`, `:394`); compare `PoachClient.lua:89-91`, which escapes names.

**How it breaks:** a display name containing `&` or `<` (if Roblox allows them in a display name) is read as rich-text markup: the row shows garbled text or broken formatting on every client in the server.

**Impact:** cosmetic; rich text can't run code. Display names are already filtered by Roblox.

**Smallest fix (S):** copy PoachClient's `escape` into IpoClient and use `escape(other.DisplayName)`.

---

## 7. Platform policy and player safety

### The Paid Random Items policy applies to this game today

Roblox clarified the policy on **2026-05-26** ([announcement](https://devforum.roblox.com/t/clarifying-requirements-for-paid-random-items/4654622), [guidelines](https://create.roblox.com/docs/production/monetization/paid-random-items)). The parts that matter here:

- A paid random item is one bought "directly with Robux, or indirectly via in-game currencies purchased with Robux, that yield a random outcome". Luck boosts are covered as probability modifiers.
- "Odds disclosures must be shown for each possible item prior to purchase. If there are many outcomes within a category, each individual outcome must still have its odds shown."
- "The probability percentages of all final outcomes must sum to exactly 100%."
- Odds modifiers "must have their effects numerically disclosed, and displayed odds must update dynamically when such items are active."
- Games with paid random items must use `PolicyService` `ArePaidRandomItemsRestricted` and keep restricted users away from them (named markets: Australia, Belgium, Netherlands, United Kingdom, Brazil).

**Why it applies:** recruiting eggs roll a random creature (`EmployeeServer.lua:226-242`) and are bought with Cash (`:310-321`). Cash is sold for Robux: Pile, Bag and Vault of Cash are **on sale now**, because `EggsEnabled = false` only hides items marked `needsEggs` (`ShopConfig.lua:16`, `:87-116`, `:182-184`). Luck Boost (Robux) is an odds modifier. So eggs are paid random items at launch whatever is decided for D4. (The free eggs from onboarding and the daily calendar are not paid.)

### FR-12 (High): the egg odds are shown per rarity, not per creature, and don't add up to 100% while a luck effect is on

> **Status:** **Fixed** in `8c1f892`: every hire is shown with its own odds (largest-remainder rounding, exactly 100.00% in every luck state, from the server's weights), the per-rarity line is their sum, Luck Boost and Talent Scouts are described in numbers; 70 checks.

**Where:** `EmployeeClient.lua:437-446` (Eggs tab), `DailyClient.lua:111-120` (daily window), both built on `CreatureConfig.getOdds` (`CreatureConfig.lua:175-191`). The server then picks a creature of the rolled rarity uniformly (`EmployeeServer.lua:240-241`).

**How it breaks the policy:**
1. **No per-creature odds.** The card shows "Common 40% · Uncommon 35% · Rare 18% · Epic 6.0% · Legendary 1.0%" for the Startup Egg. The final outcomes are the 12 creatures: each Common is 13.33%, each Uncommon 11.67%, each Rare 9%, each Epic 3%, and Unicorn CEO and Venture Dragon 0.5% each. None of these numbers is shown anywhere.
2. **Rounded numbers don't sum to 100%.** Values of 10% or more are rounded to whole numbers. With Luck Boost on:
   - Garage Egg shows 67% + 24% + 9.5% = **100.5%**
   - Startup Egg shows 32% + 28% + 29% + 9.6% + 1.6% = **100.2%**
   - Unicorn Egg shows 6.1% + 15% + 42% + 27% + 9.7% = **99.8%**
   The Talent Scouts perk (`BaseLuck`) produces other uneven sums.
3. **The modifiers are only partly described.** Luck Boost's description gives one example ("Legendary chance 8.0% -> 9.7% (Unicorn Egg)", `ShopConfig.lua:121`), true only without Talent Scouts. The Eggs tab does update live (good). Talent Scouts says "+10%" (`IpoClient.lua:139-140`), a weight change, not a probability.

**Impact:** a policy violation on the core loop. The game can be moderated or have monetization restricted; one report from a player is enough to trigger a review.

**Smallest fix (S-M, clients only):**
- Show every creature with its own odds: for each rarity, `chance / #creaturesOfRarity` per creature, e.g. "Common 40% (each 13.33%: Coffee Capybara, Coding Cat, Pixel Pigeon)". The policy allows one "odds for each item listed below" line per group.
- Show two decimals, and round with the largest-remainder method so the shown numbers always add up to exactly 100.00%.
- Luck Boost and Talent Scouts: describe the effect as numbers ("x2 weight on Rare, Epic and Legendary") and point to the live table in the Eggs tab. Keep the live update.
- Recheck with B8 on a phone.

### FR-13 (High): `ArePaidRandomItemsRestricted` is never checked

> **Status:** **Fixed** with option B (D9 decided 2026-10-02; options in docs/D9_POLICY_OPTIONS.md, `7f55d13`). `3e42a1b`: `ShopServer.setupPlayer` asks `PolicyService:GetPolicyInfoForPlayerAsync` next to the pass check, same 10 s cap, fail closed (an error, a bad or a late answer = restricted for the session), not saved, `RandomRestricted` attribute. `1afca54`: for restricted players `EmployeeServer.rollCreature` makes no random roll; each egg hires from a fixed 100-step order built from the server's weights (`CreatureConfig.fixedHire`), counted per egg in the new top-level save section `fixedHires`. `dfe412c`: Luck Boost hidden and not sold to them (its time is kept aside, never applied while restricted); Cash packs and everything else stay on sale. `ccce737`: the Eggs tab shows "Next hire from this egg" instead of odds for them. `d850a55`: restriction changes between sessions (counter never restarts, no egg lost). `94e30cf`: 175 new checks, 462/462.

**Where:** no `PolicyService` call anywhere (checked with grep over all `.lua` files). Relevant code: `ShopServer.lua:341-397` (join), `EmployeeServer.lua:310-321` (egg purchase), `ShopClient.lua:349-380` (prompts).

**How it breaks:** a player in a restricted market can buy Cash for Robux and spend it on eggs, and can buy Luck Boost once `EggsEnabled` is on. The policy says such a user "cannot interact with paid random item generators, either via in-experience currency bought with Robux or Robux directly".

**Impact:** a policy violation for the UK, Australia, Brazil, Belgium and the Netherlands, all large markets.

**Smallest fix (M):**
1. On join, call `PolicyService:GetPolicyInfoForPlayerAsync(player)` in a `pcall` (in `ShopServer.setupPlayer`, next to the pass check, with the same 10 s cap). If it fails, treat the player as restricted. Store `shop.randomRestricted` and publish it as an attribute.
2. Pick one of the treatments the policy lists, **as a decision for Mattia (new D9):**
   - (a) **No paid route to eggs:** for restricted players, hide Cash packs, Luck Boost and Instant Hatch in the shop and the Poach window, so their Cash is only earned. Cheapest (S), but ask Roblox or read the policy carefully on whether the 2x Cash and VIP passes make their Cash count as "bought with Robux".
   - (b) **Predetermined sequence:** restricted players' eggs hatch from a fixed, shown order instead of a random roll (M, in `rollCreature`).
   - (c) **Block:** refuse `BuyEgg` for restricted players; they get eggs only free (daily, onboarding). Simple, but it removes the core loop for the UK.
   My recommendation: (a) now, plus (b) if the passes count as paid.
3. Add it to the age and content questionnaire answers (C9): the game has paid random items.

### FR-14 (Low): a Robux Poach Shield is offered on a countdown while the player is being poached

> **Status:** **Skipped** (Low; decide with C8).

**Where:** `PoachClient.lua:924-951` (the red alert with a progress bar and "🛡 Shield R$ 49" during the 8-10 s negotiation).

**How it breaks:** the offer is timed and comes at a moment of loss. It is not against a rule found in this review, but it is the kind of pressure selling platform reviews and parents notice, and it matters more once under-16s unlock (ROADMAP.md:113-115).

**Smallest fix (S):** keep the shield in the Defense tab and in the "POACHED!" card afterwards, and drop the button (or the bar) from the live alert. Decide as part of C8.

### Other checks

| Check | Result |
|---|---|
| Player-written text | None. There is no `TextBox` in any client, no custom chat and no naming of startups or employees. Nothing needs `TextService` filtering. |
| Names shown | Only `DisplayName` (already filtered by Roblox) on plot signs (`TycoonCore.lua:541`), the leaderboard (FR-11) and poach messages (escaped in PoachClient). |
| Chat | Roblox's `TextChatService`; `ChatTags.lua` only adds the `[VIP]` prefix from a server attribute set from config. No chat bypass. |
| Under-16 and chat rules | CLAUDE.md has none; ROADMAP.md:113-115 says the game first reaches 16+ players. Nothing in the code depends on age. |
| Daily calendar | Free, fixed, shown in advance, no Robux in its window, odds on tap for the egg days. Fits the policy (no paid random item). |
| ShopConfig descriptions | Factual and accurate except the Luck Boost example (FR-12). "Shares", "IPO" and "stock options" are startup satire; Shares can't be traded or cashed out. Keep it that way: no wording that suggests real investing or real money. |
| Prices shown vs charged | The shop shows `ShopConfig.price`; Roblox charges the Creator Hub price. The checklist's C5 mismatch (180 / 135 / 225 on the store page) is still open. |

---

## 8. Performance and scale

### Server loops

| Loop | Interval | Work per run | Cost at 6 players |
|---|---|---|---|
| Income (`TycoonCore.lua:648-659`) | 1 s | 2 IntValue writes and 2 attribute writes per player | trivial |
| Autosave (`:662-669`) | 60 s | one save per player, one after another | 6 `SetAsync` |
| Incubators and Auto-Hatch (`EmployeeServer.lua:711-729`) | 1 s | per incubator: label text (only when it changes) and 3 property sets; `hasAutoHatch` builds a small table each time | ~30 incubators |
| Onboarding (`OnboardingServer.lua:341-355`) | 1 s | arrow target and goals, attributes only when changed | trivial |
| Daily (`DailyServer.lua:357-371`) | 1 s | `status` and ~11 attribute checks, written only when changed | trivial |
| Counter-Offer expiry (`PoachServer.lua:902-914`) | 1 s | one check per player | trivial |
| VIP lounge sweep (`ShopServer.lua:688-699`) | 0.5 s | one position check per player | trivial |
| Pass recheck (`ShopServer.lua:702-712`) | 120 s | asks Roblox about passes not owned yet, **one player at a time** (each waits for all its answers) | up to 6 x 5 web calls; slow only when Roblox is slow |

Each loop is a single thread for the whole server, not one per player. No loop yields inside its player loop except autosave and the pass recheck, and both are fine at 6 players.

### Instances and memory per player

About 370 instances per player: the plot (floor, sign, 6 upgrades, green pad), up to 5 incubators (7 instances each), the IPO and HR pads, and up to 11 employees (about 28 instances each: parts, sphere meshes and a name tag). A full server holds about 2,200. Server-side data per player is a few KB of tables. No per-player thread, connection or table outlives the player (section 6), except FR-10's empty table.

### A full server

The game supports exactly **6 players per server**: `MAX_PLOTS = 6` (`TycoonCore.lua:62`), and the 7th joiner is kicked (`:509-518`).

### FR-15 (High): nothing sets the Roblox server size to 6, but the game kicks the 7th player

> **Status:** **Documented** in docs/PUBLISH_RULES.md (`ef8edfa`). **Manual step still to do:** set Max Players to 6 in Creator Hub.

**Where:** `TycoonCore.lua:62`, `:509-518`. Not mentioned in README.md, CONTRIBUTING.md, ROADMAP.md or docs/PREPUBLISH.md (C12 says "max players" without a number).

**How it breaks:**
1. The place's **Max Players** (Creator Hub > experience > Places > the place > Max Players, or Studio Game Settings > Places) is bigger than 6. New places don't default to 6. I couldn't confirm today's default from the docs, so check the real value.
2. Roblox fills servers up to that number. Every player after the 6th gets "This server is full, please join another one" seconds after loading. Friends who "Join" each other into a full server are bounced every time.

**Impact:** at launch, a large share of joins in busy servers fail. Failed joins and short sessions also hurt Roblox's discovery signals (ROADMAP.md:38, :62).

**Smallest fix (S):** set Max Players to **6** before publishing and add it to C12 with the number. Optional code safety net: at startup, `warn` if `Players.MaxPlayers > MAX_PLOTS`. FR-3 then matters more (a slow leave save on a full server).

### FR-16 (Low): every phone animates every nearby employee every frame

> **Status:** **Skipped** (Low, first update).

**Where:** `EmployeeClient.lua:918-942`.

**How it breaks:** on every `Heartbeat`, each client moves every employee model within 160 studs of its camera with `PivotTo`. Plots are 90 studs apart, so a player usually sees 3-4 plots: up to ~44 models of ~15 parts, about 40,000 part moves per second at 60 fps. Fine on a PC; on low-end phones it costs frame rate for decoration.

**Impact:** lower FPS on cheap phones, where most Roblox players are. No gameplay effect.

**Smallest fix (S):** update walkers at about 20 Hz (accumulate `dt`), only within 80 studs, and skip models the camera can't see.

### FR-17 (Low): the shop redraws every card twice a second even when it's closed

> **Status:** **Skipped** (Low, first update).

**Where:** `ShopClient.lua:619` (`player.AttributeChanged:Connect(refreshAll)`), `:327-331`, `:421-454`; the server changes `IpoValuation` and `IpoBest` every second (`IpoServer.lua:134-135`).

**How it breaks:** every income tick changes two attributes, so ShopClient rebuilds the text of all 12 cards (with string formatting) twice per second for the whole session, window open or not. EmployeeClient and PoachClient already skip the work while their window is closed.

**Impact:** small, constant CPU and garbage on phones.

**Smallest fix (S):** in ShopClient's `refreshAll`, return early when `window.Visible` is false (the open button already calls it when opening).

---

## 9. Publish procedure

### What is live now, and why it matters

ROADMAP.md:11, :20-23 still list M4, M5, M6, #13 and #14 as "publish with **Shut down all servers**", so the version live on Roblox today is older than M4. That code has **no unknown-sections rule** (M4 F2, `2f998a7`): when it saves a player, it deletes every section it doesn't know (`ipo`, `onboarding`, `daily`) and keeps only 3 incubators. Everything below follows from that.

### The safe order (place with no live players)

**Before publishing day**
1. Finish the blockers (section "Top 10" below) and merge `prepublish-fixes` and the fixes into `main` through a PR. Release every claim in CONTRIBUTING.md.
2. Make Studio match `main` exactly (checklist A6): compare every script read-only through the Studio MCP. In Team Create, open **View > Drafts** and commit every draft: an uncommitted draft is **not** published. Neither collaborator edits during the publish.
3. Run `python tools/daily_test.py` and paste the "passed, 0 failed" lines.
4. In Creator Hub, open the place's **Version History** and write down the live version number. Call it `V_old`. Note in ROADMAP.md that it is **below the rollback floor**.
5. Settings that can't change later without side effects: **Max Players = 6** (FR-15), `DailyConfig.ResetHourUtc` (D3; moving it earlier later gives everyone an extra claim), `ShopConfig.EggsEnabled` (D4), the private/public state (stays private).

**Publishing day**
6. Check that no server runs: Creator Hub > the experience > the place's menu > **Shut down all servers** (do it even if you think none is running).
7. In Studio: **File > Publish to Roblox**.
8. Right away: **Shut down all servers** again. Use the hard shutdown, **never "Migrate to latest update"** (FR-19).
9. In Version History, write down the new version number: `V_launch`. This is the **rollback floor** (FR-18). Put it in ROADMAP.md.
10. Join the private game with a second account. Open the server log (F9 > Server). It must show no "DataStore unavailable", no "Keeping a part of ... save this version doesn't know", no "Could not set up". Rejoin and check that the IPO count, Shares, perks, daily streak and onboarding state are still there (B3, B9).
11. Real purchases with the second account (B7): one Cash pack, one pass, a Poach Shield; rejoin; nothing doubled, nothing missing.
12. Reset dev saves (B6) only with `RemoveAsync` on a written list of the dev UserIds, never a loop over unknown keys. Then the store page and the public switch (C10, C12).

### What a rollback looks like

- **Allowed:** Version History > **Restore** a version **at or above `V_launch`**, then **Shut down all servers**. Saves written by newer code keep their unknown top-level sections (F2). They do lose any *new field inside an existing section* (M4 re-review low 3), so the M9 rule A10 (new saved data gets its own top-level section) has to be followed from launch on.
- **Never:** restore `V_old` or anything older than `V_launch`. Every player who joins that version loses their `ipo` (IPO count, Shares, perks, best valuation), `daily` (streak; Day 1 becomes claimable again) and `onboarding` sections, and the eggs in incubators 4-5. When they come back to the fixed version, the IPO section is rebuilt from the capped legacy guess: Shares and perks are gone for good.
- **If data was already damaged:** Roblox keeps older versions of each DataStore key for a limited time (about 30 days). A single player's save can be restored by hand from a version (`ListVersionsAsync` / `GetVersionAsync`, or Open Cloud). Slow and manual, so the rollback floor matters more.

### If an old and a new server overlap, even for a minute

| Case | What goes wrong |
|---|---|
| A player goes from a **new** server to an **old** (pre-F2) one (a friend join, a reconnect, a soft shutdown) | The old server's first save deletes `ipo`, `onboarding`, `daily` and incubators 4-5. Back on a new server: IPO count 0, no Shares, no perks, the daily calendar back at Day 1 (an extra claim), and the eggs gone. Permanent. |
| A player goes from **old** to **new** | Fine: new code loads old saves (legacy valuation guess, onboarding counted as done for anyone with progress). |
| Both servers hold the player at once | The F10 race (section 3), between versions. |
| Two **new** versions overlap (any later update) | Only safe if the update follows A10: a field added inside an existing section is deleted by the older server. |

### FR-18 (High): there is no recorded rollback floor, and the only older version is one that wipes progress

> **Status:** **Fixed (docs)** in `ef8edfa`: docs/PUBLISH_RULES.md section 2 (rollback floor = the launch version, never older than M4); the A10 rule is in CLAUDE.md (`387b3d0`). Write `V_old` and `V_launch` on publishing day.

**Where:** process (ROADMAP.md, docs/PREPUBLISH.md); the behavior is `TycoonCore.lua:68-70`, `:304-308` (only code with these lines keeps unknown sections).

**How it breaks:** launch goes wrong on day 1 (a crash loop, a broken shop). The natural reaction is "Restore the previous version" in Version History, which is `V_old`. Every player who joins in the next minutes loses their IPO progress, Shares, perks and daily streak, permanently.

**Impact:** mass, permanent data loss from a normal emergency action.

**Smallest fix (S, docs):** steps 4 and 9 above, plus one line in ROADMAP.md and CLAUDE.md: "Never restore a place version older than `V_launch` (the first version with KNOWN_SECTIONS). Fix forward instead."

### FR-19 (Medium): a soft shutdown or a missed shutdown leaves old servers running next to new ones

> **Status:** **Fixed (docs)** in `ef8edfa`: docs/PUBLISH_RULES.md section 3 (hard shutdown only, commit drafts, check the new code is live).

**Where:** process; ROADMAP.md:22-23 says "Shut down all servers" but doesn't forbid "Migrate to latest update" or say to verify.

**How it breaks:** "Migrate to latest update" keeps old servers running until their players are moved, and a missed shutdown keeps them running until they empty. A player who reaches an old server after visiting a new one loses the new sections (table above). Also, publishing with uncommitted Team Create drafts silently publishes the old script.

**Impact:** with no live players, only the developers' saves. After launch, real players' IPO and daily progress.

**Smallest fix (S, docs):** in docs/PREPUBLISH.md B9: "Hard **Shut down all servers** only; never Migrate. Commit all drafts first. After publishing, join and check you are on the new code (for example the daily gift chip shows; old versions have none). `game.PlaceVersion` is the exact check if a one-line `print` is ever added to TycoonCore." Use the same rule for every update that changes the save.

---

## All findings

| # | Severity | Section | Where | In one line | Effort |
|---|---|---|---|---|---|
| FR-12 | **High** | 7 | `EmployeeClient.lua:437-446`, `DailyClient.lua:111-120` | Egg odds shown per rarity, not per creature, and don't sum to 100% under luck: Paid Random Items policy | S-M |
| FR-13 | **High** | 7 | no `PolicyService` call | `ArePaidRandomItemsRestricted` never checked (UK, AU, BR, BE, NL) | M |
| FR-15 | **High** | 8 | `TycoonCore.lua:62`, `:509-518` | 6 plots, but nothing sets Max Players to 6: the 7th joiner is kicked | S (setting) |
| FR-18 | **High** | 9 | process | No recorded rollback floor; restoring the live version wipes IPO, Shares and daily | S (docs) |
| FR-1 | Medium | 1 | `TycoonCore.lua:637-645`, `:352-356` | Failed saves never retried at leave; player never told; whole sessions lost in an outage | S |
| FR-4 | Medium | 3 | `PoachServer.lua:266-268`, `:452-454` | Poach chain copies an employee (3 accounts, no hop) | S |
| FR-5 | Medium | 3 | `TycoonCore.lua:241-264`, `:325-357` | No session lock: an overlapping session can wipe a paid purchase; reconnects lose up to 60 s | S interim, M lock |
| FR-19 | Medium | 9 | process | Soft shutdown or missed shutdown: old servers delete new sections | S (docs) |
| FR-2 | Low | 1 | `TycoonCore.lua:671-675` | `BindToClose` saves one by one, and twice | S |
| FR-3 | Low | 2 | `TycoonCore.lua:509-518`, `:637-645` | Plot held during a slow leave save: next joiner kicked as "server full" | S |
| FR-6 | Low | 3 | `PoachServer.lua:202-217`, `:294-311` | Attacker hop at the roll can destroy the victim's employee | lock |
| FR-7 | Low | 4 | `ShopServer.lua:483-487` | A product on sale but not in ShopConfig charges and gives nothing until Roblox refunds | S |
| FR-8 | Low | 4 | `ShopServer.lua:27`, `:413-423` | A receipt that waits > 30 s isn't retried until rejoin; no message | S |
| FR-9 | Low | 5 | `ShopServer.lua:351-356`, `PoachServer.lua:704-729`, `IpoServer.lua:350-353` | Saved numbers accept infinity (with PR14 R8) | S |
| FR-10 | Low | 6 | `ShopServer.lua:294-298` | `passConfirming` re-created after leave | S |
| FR-11 | Low | 6 | `IpoClient.lua:770` | Leaderboard names not escaped in rich text | S |
| FR-14 | Low | 7 | `PoachClient.lua:924-951` | Timed Robux shield offer during an attack | S |
| FR-16 | Low | 8 | `EmployeeClient.lua:918-942` | Employees animated every frame on phones | S |
| FR-17 | Low | 8 | `ShopClient.lua:619` | Shop redraws twice a second while closed | S |

**Counts:** Critical 0 · High 4 · Medium 4 · Low 11.

**What holds up** (checked across all systems, not one diff at a time): the all-modules-loaded save gate; receipt idempotency and grant-after-save in every order of leave/save/retry; the IPO's save-first commit, including shutdown and leave during it; the daily claim's no-yield step; server authority on every remote (no amount, price, time or result comes from a client); Studio-only debug; save size (about 11 KB, 0.3% of the limit); the DataStore budget (> 10x headroom at any server size).

## Top 10 to fix before launch, in order

1. **FR-12** Show every creature's own odds, adding up to exactly 100.00%, and describe Luck Boost and Talent Scouts in numbers. (Clients only.)
2. **FR-13** `PolicyService` check, and decide the treatment for restricted players (new decision D9; recommended: hide Cash packs, Luck Boost and Instant Hatch for them).
3. **FR-15** Set Max Players to 6 (and add it to C12 and README).
4. **FR-18 + FR-19** Write the publish rule down: record `V_old` and `V_launch`, never restore below `V_launch`, hard "Shut down all servers" only, commit Team Create drafts first.
5. **FR-4** Don't let an employee with an open `gained` note be poached or bought back.
6. **FR-1** Retry the leave save, and tell the player when saving is failing.
7. **FR-5 (interim)** Re-read the save after 7 s when it's from a session less than 75 s old. Full lock (section 3) in the first update.
8. **FR-3** Wait up to 10 s for a free plot before kicking (matters once the server size is 6).
9. **FR-7 + FR-8** Dry-run `sync_monetization` so every on-sale product is in ShopConfig (C6); wait 90 s for data in `grantProduct` and tell the player when a receipt is postponed.
10. **FR-9** One finite-number check for every saved number (closes PR14 R8 too).

FR-2, FR-6, FR-10, FR-11, FR-14, FR-16 and FR-17 can go into the first weekly update.

## Items to promote from the M9 list

| M9 item (ROADMAP.md) | Promote? | Why |
|---|---|---|
| "Read Roblox's current policy pages on rewards (Paid Random Items ...)" (`:108`) and checklist C8 | **Yes, launch-blocking**, with concrete work | Done in section 7: the game doesn't meet the 2026-05-26 clarification (FR-12, FR-13). |
| M4 re-review low 3 / checklist A10: rule that new saved data gets its own top-level section (`:76`) | **Yes, before launch** (a docs change) | Rollback is the emergency tool (FR-18), and this rule is what makes a rollback to an older-but-safe version lossless. |
| F10 session locking (`:67`, D5) | **Partly**: the interim re-read (FR-5) before launch; the full lock in the first update | D5's reasoning holds for the lock itself, but FR-5 adds a "paid and not received" case, and the interim is a few lines. |
| M5 F8 / M6 F10 (hop gives the egg or the claim twice) | No | Bounded: one reward survives. Closed by the lock. |
| PR14 R8 (IPO numbers accept infinity) | No (fold into FR-9) | Corrupt saves only; cheap to fix with the others. |
| PR14 F7 (load retry budget) | No | The current budget formula leaves > 10x headroom. |
| M4 re-review low 1 (offline Cash without pass multipliers after a slow pass check) | No | Rare, and the IPO part is fixed (`22c22ff`). |
| Everything else on the M9 list | No change | |

FR-4 is not on the M9 list: it is new, needs no hop, and the session lock does **not** fix it.

## Verdict

**Not launch-ready.** The save system, receipts and server authority are in good shape: no Critical finding, and nothing a client can call duplicates Cash or Shares. What blocks launch is outside the save code:

- **Policy:** FR-12 (odds per creature, summing to 100%) and FR-13 (`ArePaidRandomItemsRestricted`). Eggs are paid random items today because Cash packs are on sale, whatever D4 decides.
- **Settings:** FR-15 (Max Players 6).
- **Procedure:** FR-18 (rollback floor) and FR-19 (hard shutdown only).
- **Cheap code fixes worth doing first:** FR-4 (employee copy) and FR-1 (silent session loss).

After those, and the open checklist blockers (C1-C5, C8, C9, B1-B9), the game is ready to publish.

## Sources

- [Data stores: error codes and limits](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) (budgets, per-key limits, 30-request queues, 4 MB)
- [Paid random items policy guidelines](https://create.roblox.com/docs/production/monetization/paid-random-items)
- [Clarifying Requirements for Paid Random Items](https://devforum.roblox.com/t/clarifying-requirements-for-paid-random-items/4654622) (2026-05-26)
- [MarketplaceService.ProcessReceipt](https://create.roblox.com/docs/reference/engine/classes/MarketplaceService#ProcessReceipt) and [DevForum: NotProcessedYet retries](https://devforum.roblox.com/t/developer-product-purchases-returned-as-notprocessedyet-not-being-retried/3502516) (retry on rejoin, ~3-day refund; not in the API docs)
