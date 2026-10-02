# Pre-publish results: Studio-free part of group A

Run on 2026-10-02 from branch `claude/prepublish-results` (cut from `claude/prepublish-checklist`, so it has the same code as `main` plus the checklist). Read-only: no `.lua` file changed, no Studio, no Roblox API call.

| # | Item | Result |
|---|---|---|
| 1 | `tools/daily_test.py` | **PASS** |
| 2 | Debug tools can't run on a live server | **PASS** |
| 3 | Real IDs for every pass and product | **PASS (format) / NOT VERIFIED against Roblox** |
| 4 | Egg odds in UI and text match config | **PASS** |
| 5 | Paid-pass check when Roblox is slow | **Fixed** in `6b3abb2` (was FAIL); Shares follow-up fixed in `22c22ff` |
| 6 | `data.saving` can stick | **Fixed** in `ebe59cd` (was FAIL) |
| 7 | Remote exploit sweep, code side | **PASS**, with 2 minor notes |

---

## 1. daily_test.py: PASS

Luau (latest macOS release) installed in the session scratch folder, not in the repo. `LUAU=<path> python3 tools/daily_test.py` printed:

```
69 passed, 0 failed
TycoonCore save check: 22 passed, 0 failed
TycoonCore store check: 13 passed, 0 failed
```

69 + 22 + 13 = 104 / 104, the same count the checklist expects.

## 2. Debug tools on a live server: PASS (no path reaches a live server)

Layers, in the order a client request meets them:

1. **Registration:** the remote `ShopDebug` is created only if `RunService:IsStudio() and ShopConfig.DebugInStudio` ([ShopServer.lua:593](../ShopServer.lua#L593)). It is the **only** remote through which any debug handler can run: `extraDebugActions` is read only inside `handleDebug` ([ShopServer.lua:563](../ShopServer.lua#L563)).
2. **Handler guard:** `handleDebug` re-checks `not IsStudio() or not DebugInStudio` and returns "Debug is disabled" ([ShopServer.lua:525](../ShopServer.lua#L525)). It also checks `typeof(action)`/`typeof(key)` and `data.ready`.
3. **Registration of extra actions:** every module registers its `addDebugAction` calls only inside `if RunService:IsStudio()`: EmployeeServer:684, IpoServer:443, OnboardingServer:330, PoachServer:876, DailyServer:352.
4. **Per-handler IsStudio:** only the two DailyServer handlers repeat it ([DailyServer.lua:320,331](../DailyServer.lua#L320)). The others rely on layers 1-3.
5. **Client:** `ShopClient` sets `debugRemote = RunService:IsStudio() and remotes:FindFirstChild("ShopDebug") or nil` ([ShopClient.lua:15](../ShopClient.lua#L15)); the Debug tab and all its rows exist only `if debugRemote`.

| Handler / row | Layers |
|---|---|
| IgnoreRealPasses, TogglePass, GrantProduct, RepeatReceipt (ShopServer) | 1, 2, 5 |
| GiveCash (amount capped 1e9), ForceRarity, SkipEggTimers (EmployeeServer) | 1, 2, 3, 5 |
| IpoGrantValuation, IpoJumpReady, IpoGrantShares, IpoReset, IpoFailNextSave | 1, 2, 3, 5 |
| OnboardingRestart, OnboardingMarkOld | 1, 2, 3, 5 |
| PoachSpawnDummy, PoachDummyHR, PoachDummyAttack, PoachForce, PoachClearTimers | 1, 2, 3, 5 |
| DailyNextDay, DailyReset | 1, 2, 3, **4**, 5 |

Other debug state: `data.debugFailIpoSave` (TycoonCore:321), `team.forceRarity`, `poach.forceResult`, `ignoreShields` are only set by those handlers, so a live server can never set them. `ShopConfig.DebugInStudio = true` is safe because `IsStudio()` is the deciding check. Weakest point: five modules have no handler-level guard, so a future edit that makes `extraDebugActions` reachable another way would expose them. Not a bug today.

## 3. Pass and product IDs: PASS on format, NOT VERIFIED against Roblox

Read from [ShopConfig.lua](../ShopConfig.lua) only (no API call, as instructed):

- 6 passes: DoubleCash 1998261947, VIP 2002622694, ExtraSlots 1998075790, AutoHatch 2002694731, Headhunter 1998465892, Shareholder 2001728902.
- 6 products: CashSmall 3715692111, CashMedium 3715692112, CashLarge 3715692113, LuckBoost 3715692114, InstantHatch 3715692116, PoachShield 3715702908.
- None is `0` or a placeholder; all 12 are different (the file's own duplicate check would `warn` otherwise). Product ...115 is skipped; harmless, but it may be a deleted product.
- I **could not confirm each ID matches what Roblox has**: that needs the API (or `sync_monetization.py` with no changes), which this run was told not to use. To close it: run `sync_monetization.py --dry-run` (or compare by hand in Creator Hub) and check the 4 `needsEggs` items are **off sale** while `EggsEnabled = false`.

## 4. Egg odds: PASS

All three eggs' weights add up to exactly 100, so the UI percentages equal the config numbers. The UI (`EmployeeClient.oddsText`) computes from `CreatureConfig.getOdds`, the same function the server rolls with (`rollCreature`), so shown odds and real odds cannot drift. Luck Boost (x2 on Rare/Epic/Legendary) recomputed:

| Egg | Legendary normal | Legendary with Luck Boost |
|---|---|---|
| Garage | 0% | 0% (Rare 5.0% -> 9.5%) |
| Startup | 1.0% | 1.6% |
| **Unicorn** | **8.0%** | **9.70%** |

The only hard-coded numbers in text are in the Luck Boost description ("Legendary chance 8.0% -> 9.7% (Unicorn Egg)", [ShopConfig.lua:97](../ShopConfig.lua#L97)): both correct. They would go stale if Unicorn odds or `luckMultiplier` change. Note: the Talent Scouts IPO perk (`BaseLuck`) stacks on top, in both the UI and the server, so a player with that perk sees and gets more than 9.7%. The text doesn't mention it; fine.

## 5. Paid-pass check timeout: Fixed in `6b3abb2` (was FAIL)

**Fix (branch `prepublish-fixes`, ShopServer + ShopConfig):**
- After a purchase, `confirmPurchasedPass` asks Roblox every `ShopConfig.PassConfirm.RetrySeconds` (5) for up to `GiveUpSeconds` (120). The pass is granted only when Roblox answers yes (a "no" or an error just means ask again), so server authority is unchanged. The player sees "Confirming ... with Roblox...", then "... unlocked!", or after 2 minutes "Roblox is slow to confirm ...", and the 120 s recheck loop or a rejoin still picks the pass up. One confirmation runs per player and pass.
- `checkPasses` now asks all passes at the same time and calls `publish` as each one is found. With Roblox down the join check takes about 6 s instead of 36 s, so it finishes inside the 10 s join timeout.
- **Join-time findings:** (a) *VIP lounge:* the collision group already blocks a player whose pass isn't known yet, so a VIP owner can't walk in and be thrown out; but the door would offer to *sell* the pass to an owner, and the lounge sweep could move out someone inside. Both now wait while `ShopServer.isPassCheckPending(player)` is true. (b) *Shareholder 2x Shares:* **Fixed in `22c22ff`.** `IpoServer.goPublic` refuses with "One moment: still checking your game passes with Roblox" while `ShopServer.isPassCheckPending` is true (refusing, not waiting, so nothing yields between the checks and `ipo.busy`). A stuck check stops blocking after `IpoConfig.PassCheckMaxWaitSeconds` (20 s).

Original finding, kept for the record:

What the code does ([ShopServer.lua:231-330](../ShopServer.lua#L231)):

**Joining with passes already owned, Roblox slow or erroring.** `setupPlayer` starts `checkPasses` in a thread and waits at most `PASS_CHECK_TIMEOUT` = 10 s, then loads the player without passes. Each pass is asked one after the other, and a failing ask is tried 3 times with waits of 1 s and 2 s and 3 s, so one failing pass takes 6 s or more, and six passes at least 36 s. Until the whole loop finishes **nothing is published**: even if the 2x Cash answer came back at second 3, the attribute stays off until the sixth pass is done. Meanwhile the player has no Cash multiplier, no VIP, no Headhunter, no Shareholder. Worst cases:
 - A VIP owner who walks into the lounge is **teleported out** with "for VIP holders only" (`hasEffect` is false).
 - If they **go public in that window**, Shares are not doubled, and that loss is permanent.
 - Passes aren't saved, so after the answer arrives all is fixed, but the 2x Cash and Shares earned in the window are lost.
 - If every call fails for good, the next retry is the 120 s recheck loop (`PASS_RECHECK_SECONDS`).

**Buying a pass while Roblox is slow.** `onPassPromptFinished` runs `userOwnsPass` (3 tries). If all fail it returns `nil`, and the function **silently does nothing**: Robux is spent, no "unlocked" message, no pass. The event does not fire again. The player gets it at the next 120 s recheck, with no message (the recheck publishes but doesn't call `notify`), or on rejoin. A paying customer sees nothing for up to 2+ minutes. This is the case that matters most.

**Smallest fix (two small edits, both in ShopServer.lua):**
1. In `onPassPromptFinished`, when `wasPurchased` is true and `userOwnsPass` returns `nil`, retry in a loop (for example every 5 s for up to 2 minutes, `task.spawn`) and grant + `notify` when it says true. Keep the ownership re-check, as CLAUDE.md requires.
2. In `checkPasses`, call `publish(player)` as soon as each pass is found (or move the `gaveUp` publish into the loop), so one slow pass doesn't hold back the others. Optional if (1) is done.

## 6. `data.saving`: Fixed in `ebe59cd` (was FAIL)

**Fix (TycoonCore):** the payload build and the IPO `transform` moved into `buildPayload`, which runs them in a `pcall`. On an error it warns, sets `data.saving = false` and `save()` returns false. The payload is a local that only exists whole, and the serializers return fresh tables, so a failed build writes nothing and leaves the live data untouched. The bounded wait on `data.saving` was not added.

Original finding, kept for the record:

[TycoonCore.lua:292-331](../TycoonCore.lua#L292): `save()` sets `data.saving = true`, then builds the payload by calling `ShopServer.serialize`, `EmployeeServer.serialize`, `PoachServer.serialize`, `IpoServer.serialize`, `OnboardingServer.serialize`, `DailyServer.serialize` and the IPO `transform` **outside any `pcall`**; only `SetAsync` is protected. If any of those throws (a bad value in a section, a nil field), the thread dies with `data.saving` still `true`. Every later `save()` for that player then runs `while data.saving do task.wait() end` **forever**: autosave, "save now" after spending Shares, the IPO commit (the player is stuck with `data.ready = false`), the save when leaving, and `BindToClose` would hang until Roblox cuts the server at 30 s. Nothing is written for the rest of the session, with no message beyond the original error.

**Smallest fix:** build the payload (and run `transform`) inside a `pcall`. If it fails, `warn`, set `data.saving = false` and `return false`. A one-line extra: bound the `while data.saving` wait (for example, give up after 30 s with a warning) so a stuck flag can never hang the server.

## 7. Remote sweep, code side: PASS (2 minor notes)

There is **no `OnServerEvent`** anywhere in the code. Every `RemoteEvent` is server -> client only, so a client cannot send anything through them. The only client -> server entry points are the `RemoteFunction`s below (all `OnServerInvoke`). All of them first check `typeof(action) == "string"` and `data.ready`.

| Remote (RemoteFunction) | Actions | Argument checks |
|---|---|---|
| `ShopRemotes.ShopDebug` | debug only (Studio, see item 2) | string types, Studio guard |
| `EmployeeRemotes.EmployeeAction` | `Sync` (no arg); `BuyEgg(eggKey)`: type string + config lookup, then server checks cash and a free incubator; `Hatch(i)`, `InstantHatch(i)`: number, whole, 1..incubatorCount, then ready/pending/token checks; `Fire(id)`, `ResolvePending(choice)`: type string, looked up in the team, no match -> refused | all checked; unknown action refused |
| `PoachRemotes.PoachAction` | `Targets`: rate-limited (`TARGETS_MIN_INTERVAL`); `Start(userId, employeeId)`: number and string, `#b <= 64`, then target online, protected/busy, cost, cash, slot; `CounterOffer`: no arg | NaN/inf/float userId only fails the player lookup; all checked |
| `IpoRemotes.IpoAction` | `Preview`: no arg, read-only; `GoPublic(n)`: number and must equal `count + 1`, then cooldown, valuation, busy, loaded; `BuyPerk(key)`: string + config lookup, level and Shares | all checked |
| `OnboardingRemotes.OnboardingAction` | `DismissTracker`: no arg | all checked |
| `DailyRemotes.DailyAction` | `Claim` only; debounce `ClaimDebounce`; needs `ready` and `loaded` | all checked; extra args ignored |

Prices, odds, cash, timers and rewards are all server-side; no remote carries an amount from the client.

Notes, not blockers:
- **No size limit on string args** in `Fire`, `ResolvePending`, `BuyEgg`, `BuyPerk` (only `Start` limits to 64). They are used only as table-lookup keys, so a long string costs one failed lookup; adding `#arg <= 64` is a one-line hardening.
- **No rate limit** on `BuyEgg`, `Hatch`, `Fire`, `Sync`, `Preview`, `BuyPerk`, `GoPublic`. Each call is cheap or has its own cost/lock, so spamming can't duplicate anything; `Sync` and `Preview` could add server load. Worth a throttle only if you see abuse.
- Not tested live: this is a code read. The checklist's A3 (firing the remotes from a client with NaN, huge numbers, tables, spam) still needs a 2-player Studio session if you want runtime proof.

---

## Needs a code fix before publish (items 1 and 2 are now fixed on `prepublish-fixes`; sync ShopServer, ShopConfig and TycoonCore to Studio)

1. **Item 5, paid pass (ShopServer):** retry the ownership check after a purchase event when Roblox didn't answer, then grant + notify; optionally publish per pass. Customers pay and see nothing for 2+ minutes today.
2. **Item 6, `data.saving` (TycoonCore):** wrap the payload building and `transform` in `pcall`, reset `saving` and return false on error (optional bounded wait).
3. **Item 3, not a code fix:** confirm the 12 IDs and sale state against Roblox (`sync_monetization.py --dry-run` or Creator Hub) before publishing.

Both code fixes need the owner's claim in CONTRIBUTING.md and a Studio sync. Items 1, 2, 4 and 7 need no change.
