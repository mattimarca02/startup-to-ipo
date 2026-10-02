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

**Where:** `TycoonCore.lua:241-264` (load reads without any lock), `:325-357` (blind `SetAsync`), `ShopServer.lua:461-480`.

**How it breaks (purchase):**
1. Device 1 is in server A. Device 2 joins server B; B reads the save (without the purchase below).
2. Before Roblox kicks device 1, the player buys a Cash pack (or Instant Hatch, Poach Shield) on device 1. A grants it, saves, answers `PurchaseGranted`.
3. B never sees the purchase. B's autosave overwrites A's save. Roblox won't send the receipt again.

**How it breaks (no exploit, normal players):** the client loses its connection; the player taps Reconnect and lands in a new server while the old server still holds them (it takes a while to notice). The new server reads the last autosave (up to 60 s old). The old server's leave save lands later and is then overwritten by the new server's autosave. Up to 60 s of progress is lost. If the old server's write is stuck in a throttle queue and lands *after* the new session's last save, the whole new session is lost.

**Impact:** paid and not received (rare, two devices at once); "I lost my last minute" after reconnects (common enough to cause reviews); the M4 F10 / M5 F8 / M6 F10 hops above.

**Smallest fix:** the lock below (M). If it can't make launch, an interim (S): on join, if `os.time() - saved.lastSeen < 75` (the save may come from a session that is still running), wait 7 s and read again before setting up. It costs every quick rejoin 7 s of loading but removes most reconnect losses. It does not stop the two-device purchase case.

### FR-6 (Low): an attacker who hops at the exact moment of a poach can destroy the victim's employee

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

**Where:** `ShopServer.lua:483-487`, `ShopConfig.lua:176-179`.

**How it breaks:** any product on sale in the universe whose ID isn't in `ShopConfig.Products` (an old test product, the skipped `3715692115` if it still exists and is on sale, a product created in Creator Hub but not synced) answers `NotProcessedYet` forever with only a server warning. Roblox keeps retrying and refunds the Robux after about 3 days (DevForum; the API docs don't state it). Players reach such a product only through a prompt the game doesn't show, so today this needs a stray prompt (another game's or a Roblox page linking it).

**Impact:** a confused paying player and a support request. No Robux kept.

**Smallest fix (S):** before launch, run `sync_monetization.py --dry-run` (checklist C6) and take every product that isn't in ShopConfig off sale. Optional: in `processReceipt`, `notify` the player "This item isn't sold here anymore; Roblox will refund it" for an unknown product.

### FR-8 (Low): a receipt that waits more than 30 s is not retried until the player rejoins, and nobody tells them

**Where:** `ShopServer.lua:27` (`DATA_WAIT_SECONDS = 30`), `:413-423`, `:462-465`.

**How it breaks:** the player buys right after joining while the join is slow (3 load tries with 6 s of waits, the 10 s pass check, a `reconcile` read during DataStore trouble), or during an IPO save stuck in the throttle queue. After 30 s the receipt answers `NotProcessedYet`. Roblox retries only on the player's next join or next purchase. The purchase dialog said "success" and the game shows nothing.

**Impact:** a paying player waits until they rejoin (or loses the purchase to Roblox's ~3-day refund if they never come back). Rare: needs a slow join or a slow IPO save.

**Smallest fix (S):** raise `DATA_WAIT_SECONDS` to 90, and when answering `NotProcessedYet` while the player is still in the server, `notify` them: "Your purchase will arrive when your game finishes loading. If it doesn't, rejoin."
