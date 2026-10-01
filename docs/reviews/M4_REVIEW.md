# M4 review: IPO rebirth

PR #6, branch `milestone-4-ipo`. Code reviewed at commit `e9be034`. All `file:line` references point at that commit.

**Status: complete.** Ranked findings and the verdict are in sections 8 and 9.

## Severity scale

| Level | Meaning |
|---|---|
| Critical | A client can cheat, or player data or Robux value is lost or duplicated in a normal situation. Blocks the merge. |
| High | A bug that normal players will hit. Should block the merge. |
| Medium | A real bug in an uncommon situation, or the code does something different from what ROADMAP promises. Fix before launch. |
| Low | A rare edge case, a confusing message, or a safety net that's missing. Fix when convenient. |

## 1. Findings from the first pass

These were found before the review was interrupted. Each one was checked again against the code at `e9be034`.

### F1 (Medium): an IPO resets the HR Department, but ROADMAP says it's kept

- **Where:** `TycoonCore.lua:248-250` (the save written during the IPO sets `hrLevel = 0`), `TycoonCore.lua:264` (calls `PoachServer.resetHrDepartment`), `PoachServer.lua:628-637` (the reset itself). The texts say the same: `IpoClient.lua:491`, `IpoClient.lua:602`, `IpoConfig.lua:6`.
- **What breaks:** ROADMAP M4 says "Keeps employees, passes, owned products and HR level". The code does the opposite. The player loses up to $522,500 of HR levels, and loses their poaching defense right when they restart with $0 and can't buy it back.
- **Fix:** delete the two reset spots in TycoonCore and `resetHrDepartment` in PoachServer, then update the three texts. Consider a short Poach Shield after every IPO (duration in `IpoConfig`), so a fresh start isn't an easy target.

### F2 (Medium): `save()` throws away any save section it doesn't know

- **Where:** `TycoonCore.lua:203-211` builds the payload only from the sections this version knows. `EmployeeServer.lua:498-502` drops saved incubators above the current count, and `EmployeeServer.lua:529` saves only up to that count.
- **What breaks:** code that doesn't know a section deletes it on the next save. Two real cases:
  1. **Publishing M4.** Servers still running the old code keep going until they close. A player who goes public on a new server, then joins an old one, loses the whole `ipo` section on that server's next save: IPO count, Shares and perks. The old code also knows only 3 incubators, so eggs in incubators 4 and 5 are lost too.
  2. **Rolling back** to an older version after a bad publish does the same.
- **Fix:**
  - In `save()`, copy back every top-level section of the loaded save that this version doesn't recognise, with a warning.
  - Keep incubators 4 and 5 working.
  - Add the rule to CLAUDE.md's save rules.
  - The old code can't be changed, so when M4 is published, use **Shut down all servers** (or Migrate to Latest Update). The game isn't launched yet, so only dev saves are at risk today.

### F3 (Low): an open Counter-Offer isn't covered by the IPO lock

- **Where:** `PoachServer.lua:615-626` (`isBusy` ignores `poach.counterOffer`). `PoachServer.lua:466` checks only `isOnline(attacker)`, and `PoachServer.lua:104-107` only checks that the poacher's data exists, not `data.ready`.
- **What breaks:**
  - **The poacher loses the Cash.** Player A poached from B and is now going public (`data.ready = false`, save in flight). B makes the Counter-Offer. It goes through, because nothing checks A's `ready`. In `transfer` (`PoachServer.lua:257-266`), A gets the payment once B's save lands. If that happens before A's IPO save finishes, `commitIpo` then sets A's Cash to 0 (`TycoonCore.lua:257`), so A loses the payment B made. It also breaks the promise in `IpoServer.lua:183` that "poaching waits" during an IPO.
  - **The victim loses the buy-back.** If B goes public while their own Counter-Offer is open, the IPO is allowed and resets B's Cash to 0. B can no longer afford to buy the employee back, and nothing warned them.
- **Fix:** count `poach.counterOffer` in `isBusy`, and refuse a Counter-Offer while the poacher's `data.ready` is false. Refuse with "try again", don't drop the offer.

### F4 (Low): the confirm screen doesn't say how many eggs will be lost

- **Where:** `IpoClient.lua:594-614` (confirm text), `EmployeeServer.lua:543-553` (`clearIncubators`).
- **What breaks:**
  - The screen only says "eggs in incubators". Eggs that are ready to hatch are wiped without a specific warning. That includes ready eggs that are waiting because a new hire is still pending (`EmployeeServer.lua:250`).
  - The Cash amount on the screen is fixed when the screen opens (`IpoClient.lua:605`). If a Cash pack lands during the 15 seconds the screen stays open, the screen shows less Cash than the IPO actually wipes.
  - *Correction to the first pass:* this does **not** affect Instant Hatch. Instant Hatch hatches the egg straight away (`EmployeeServer.lua:313-314`), so a Robux-paid hatch is never left in an incubator.
- **Fix:** have the server send the number of incubating and ready eggs for the confirm screen. Show the count, plus a red warning if any are ready.

### F5 (Low): saves from before M4 get an uncapped starting valuation

- **Where:** `TycoonCore.lua:382-391`.
- **What breaks:** an old save's valuation is its Cash plus the cost of its upgrades, with no limit. Before M4, Cash had nothing to buy late in the game (ECONOMY.md finding 3), so an old save can hold hundreds of millions. That save is IPO-ready on its first join, and Shares grow with valuation (`IpoConfig.lua:124-127`). A $250M save gets 100 Shares on its first IPO, enough for a large part of the IPO shop (525 Shares buys everything). Its leaderboard "best" is inflated the same way. Only dev saves exist today.
- **Fix:** `legacyValuation = math.min(legacyValuation, IpoConfig.ipoValuation(0))`.

### F6 (Low): an unfinished poach transfer can cross an IPO

- **Where:** `PoachServer.lua:615-626` (`isBusy` checks only the in-memory `inTransit` list of this server), `PoachServer.lua:281-298` (`reconcile` on the next join).
- **What breaks:** if a server stops halfway through moving an employee, a `gained` note stays in the save, and nothing stops an IPO. On a later join, `reconcile` can hand the employee back and refund Cash paid before the IPO into the new run. It needs a server crash at exactly the wrong moment, and the amount is one poach cost.
- **Fix:** accept it and list it under "Known low risks" in ROADMAP. Blocking IPOs while a `gained` note exists is worse, because a note can stay for a long time if the other save can't be read.

### F7 (Low): small things

- **Wrong message during an IPO.** `IpoServer.lua:235` answers "Still loading" while an IPO is being saved (`data.ready = false`), so the "Your IPO is already being filed" check at `IpoServer.lua:157` can never run. `EmployeeServer.lua:410` and `PoachServer.lua:543` show the same "Still loading" during an IPO. **Fix:** show "Your IPO is being filed" when the IPO is the reason.
- **`addEarnings` accepts NaN.** At `IpoServer.lua:124-134`, NaN passes `amount <= 0`. A NaN valuation then passes the `ipo.valuation < needed` check (`IpoServer.lua:165`), because every comparison with NaN is false. `sharesFor` turns it into NaN Shares, which pass `ipo.shares < cost` (`IpoServer.lua:222`), so every perk becomes free. No caller can send NaN today (Income is an IntValue, and Debug amounts are checked), so this is a missing safety net, not a live bug. **Fix:** reject `amount ~= amount` and `math.huge`.
- **`IpoServer.isBusy` is never used.** See `IpoServer.lua:11` and `IpoServer.lua:119-121`. **Fix:** remove it, or use it for the message fix above.

### F8 (balance, not a bug): every run gets much longer

- **Where:** `IpoConfig.lua:25` (`StageGrowthPerIpo = 1.5`), `IpoConfig.lua:31` (`BonusExponent = 0.75`).
- **What happens:** by IPO 10 the stages are 1.5^9 = 38x bigger, but the multiplier is only x3.6. Employee income is capped by the slots, so the 10th run takes roughly 10x longer than the first.
- **Suggestion:**
  1. Try `StageGrowthPerIpo = 1.3` and `BonusExponent = 1`.
  2. Point the IPO section of `tools/economy_sim.py` (on `main`) at the real `IpoConfig` values. Its IPO numbers are still placeholders.
  3. Rerun it and put the time to IPO 1, 3, 5 and 10 in `docs/ECONOMY.md`.

## 2. Server authority

**Question:** can a client trigger or fake an IPO, or skip one of its requirements?

**Answer: no way found.** Every check runs on the server:

| What a client could try | What stops it |
|---|---|
| Send `GoPublic` without opening the confirm screen | Allowed, but it's the player's own choice. The server still checks everything below. |
| Go public before IPO-ready | `IpoServer.lua:164-167` compares the server's own valuation. |
| Go public twice (repeat or old request) | The IPO number must be `count + 1` (`IpoServer.lua:154`), and there's a 60-second cooldown (`IpoServer.lua:159-163`). |
| Go public during a deal | `core.isPoachBusy` (`IpoServer.lua:168`). See F3 for the Counter-Offer gap. |
| Go public with a save that failed to load | `data.loaded` (`IpoServer.lua:158`). |
| Fake the valuation, Shares or perks | They exist only on the server. The `Ipo*` attributes are copies for display, and no server script reads player attributes back. The only server `GetAttribute` is on a creature model (`EmployeeServer.lua:176`). |
| Buy a perk without Shares, past max level, or an unknown one | `IpoServer.lua:214-223` checks the key type, the perk, the level and the Shares. |
| Use the Debug tab on a live server | The debug remote only exists in Studio (`ShopServer.lua:578-583`), the handler checks again (`ShopServer.lua:504`), and IpoServer adds its Debug actions only in Studio (`IpoServer.lua:413-415`). |
| Spam the gold pad | It only opens the window, at most every 3 seconds (`IpoServer.lua:281-286`). |

The only open item here is F7's NaN safety net, which no client can reach today.

## 3. Data integrity

### What holds up

- **Double-firing.** A second `GoPublic` while the first is saving is refused because `data.ready` is false (`IpoServer.lua:235`). After the first one finishes, the old IPO number is refused (`IpoServer.lua:154`). Two `BuyPerk` calls run one after the other without yielding, so each one checks the Shares again.
- **Leaving during the IPO save.** The leave save waits for the save lock (`TycoonCore.lua:194-197`). `commitIpo` applies the reset without yielding (`TycoonCore.lua:257-266`), and so does `goPublic` (`IpoServer.lua:187-209`). So the leave save always writes the state after the IPO.
- **Server shutdown during an IPO.** It works the same way: `BindToClose` saves wait for the lock. If the server dies first, either the IPO save landed in full or it didn't land at all.
- **A save that reports failure but actually landed.** Nothing changes in memory, and the next save writes the state from before the IPO. The IPO is undone, not doubled.
- **Old saves.** A save without `ipo` gets a guessed valuation (see F5 for the missing cap).
- **A broken `ipo` section.** A non-table is treated as "no IPOs yet". Negative numbers and NaN become 0. Unknown perks are skipped with a warning (`IpoServer.lua:306-326`). IpoServer's own loading is solid.

### F9 (High): a player who leaves while their save is still loading loses employees, poaching data and IPO progress

This is older than M4, but M4 adds the most valuable part of the save to what's lost.

- **Where:**
  - `TycoonCore.lua:374` sets `data.loaded = ok` **before** the modules set up their parts of the save (`TycoonCore.lua:381-394`).
  - The first of those, `ShopServer.setupPlayer`, waits for Roblox. It calls `checkPasses` (`ShopServer.lua:307`), which makes about 5 `UserOwnsGamePassAsync` web calls on every join (`ShopServer.lua:245-254`). When Roblox's servers are slow, those calls are retried with waits of 1, 2 and 3 seconds (`ShopServer.lua:230-241`).
- **What breaks:** while those calls are running, `data.team`, `data.poach` and `data.ipo` don't exist yet, but `save()` is already allowed. If the player leaves (or the server shuts down) in that moment, the save written on leaving has Cash, upgrades and the shop, and **no `team`, `poach` or `ipo`** (`TycoonCore.lua:203-211`, where each `serialize` returns nil). Their employees, eggs, HR level, IPO count, Shares and perks are gone for good.
  - The window is usually under a second. During a Roblox web outage it can reach about 30 seconds, which is exactly when players leave and rejoin.
  - An autosave in that window writes the same incomplete save. The next save fixes it, but a server crash in between makes the loss permanent.
- **Same root cause, two more ways in:**
  1. **A broken section stops the setup with an error.** For example, `shop.luckLeft` stored as text makes `luckLeft > 0` error (`ShopServer.lua:284-285`), or `team.incubators` that isn't a table makes `ipairs` error (`EmployeeServer.lua:498`). `data.loaded` is already true, so the next autosave overwrites the save without the sections that never loaded. CLAUDE.md says bad values must be "skipped with a warning, never an error".
  2. **A poaching note can be lost.** `PoachServer.setupPlayer` holds the `gained` notes in a local table (`PoachServer.lua:656`) while `reconcile` waits for the other player's save (`PoachServer.lua:283`). If the player leaves then, the leave save has no `gained` notes, so an unfinished employee move can never be undone (it can stay duplicated).
- **Fix:**
  - Set `data.loaded` only after every `setupPlayer` has finished, right before `data.ready = true` (`TycoonCore.lua:416`). Use the local `ok` in between.
  - Run the setup inside `pcall`. If it errors, keep `loaded = false` (so this session never overwrites the save) and warn.
  - In `reconcile`, keep each note in `data.poach.gained` until that note is resolved.
- **Not tested in a playtest on purpose:** Studio uses the real DataStore, so reproducing this would overwrite Mattia's real save. It's verified by reading the code. The cause is an `...Async` call, and those always yield.

### F10 (Low): leaving mid-IPO and joining another server straight away can undo the IPO

- **Where:** there's no session lock, so two servers can hold the same save. This is already planned for M9.
- **What breaks:** the second server can read the save before the first server's IPO save lands. It then plays on with the state from before the IPO, and its saves overwrite the IPO. Nothing is duplicated (the Shares from the lost IPO are lost too), and the player can go public again.
- **Fix:** M9 session locking. Nothing to do in M4.

## 4. Reset scope

Checked against the save written during the IPO (`TycoonCore.lua:240-252`) and the in-game reset after it (`TycoonCore.lua:257-266`, `IpoServer.lua:196-203`).

| Item | ROADMAP M4 says | Code does | OK? |
|---|---|---|---|
| Cash | reset | set to `IpoConfig.StartingCash` (0) | ✅ |
| Garage upgrades and their parts | reset | `owned` emptied, parts destroyed | ✅ |
| Green pad | reset | back to the free Desk | ✅ |
| Eggs in incubators (incl. Extra Incubator slots) | reset | all set to `false` | ✅ (see F4 for the warning) |
| Valuation | reset | 0. `lifetime` and `best` are kept | ✅ |
| **HR Department level** | **kept** | **reset to 0** | ❌ **F1** |
| Employees, outgoing employees, waiting new hire | kept | not touched | ✅ |
| Game passes | kept | not saved, checked again on every join | ✅ |
| Luck Boost time, Instant Hatches, receipts | kept | `shop` section not touched | ✅ |
| Poach Shield time, poach cooldown, losses, gained/lost notes | kept | `poach` not touched (except HR) | ✅ |
| Shares, perks, IPO count | kept, plus the reward | `count + 1`, `shares + reward`, perks copied | ✅ |
| Income multiplier | grows | `updateIncome` runs after the IPO (`IpoServer.lua:203`) | ✅ |

**Result:** IPO wipes exactly what it should, except the HR level (F1). The in-game texts list the same things as the code, so they will need updating when F1 is fixed.

## 5. Interaction with M2 eggs and M3 poaching

### Eggs

- **`EggsEnabled = false`** only hides the Robux egg items. Eggs bought with Cash in the garage still work, and the IPO clears them. That's correct, because they belong to the run that resets.
- **Instant Hatch** is safe (see the F4 correction). Eggs that are ready but stuck behind a pending new hire are wiped, and that's what F4's warning is for.
- **IPO perks:** Extra Incubator, Extra Desk, Faster Recruiting and Talent Scouts are all read on the server (`EmployeeServer.lua:53`, `:58`, `:230`, `:297`). IpoServer is set up before EmployeeServer (`TycoonCore.lua:392-393`), so incubators 4 and 5 load with their eggs. Older code drops them, which is part of F2.

### Poaching

| Question | Answer |
|---|---|
| Can an in-flight poach cross an IPO? | No. A running negotiation blocks the IPO for both the poacher and the target (`PoachServer.lua:618`), and so does an employee that's still being moved on either team (`PoachServer.lua:619-624`). |
| Can someone start poaching a player while their IPO is saving? | No. `poachOf` needs `data.ready` (`PoachServer.lua:86`), so the target shows as "Still loading". |
| Can an IPO duplicate or delete an employee? | No. The IPO never touches the employee list (`TycoonCore.lua:240-252`). |
| Can a Counter-Offer slip through an IPO? | Yes, with a small Cash loss in a narrow race: **F3**. |
| Can an unfinished move from a crashed server cross an IPO? | Yes, with a small refund into the new run: **F6**. |
| Recruiter Network perk | Lowers the poach cost. A refund always returns what was actually paid (`negotiation.cost`). Consistent. |

## 6. Monetization: the Shareholder pass

**Result: a clearly marked placeholder, with no live calls that could fail.**

- **Clearly marked.** `ShopConfig.lua:70-78` has `id = 0` and a comment saying the owner runs `sync_monetization` on the PC. ROADMAP's Status lists it as NOT SYNCED.
- **Can't be bought.** `ShopConfig.isForSale` is false for `id = 0` (`ShopConfig.lua:179`), so the shop shows "Coming soon" (`ShopClient.lua:426-427`) and `promptPurchase` stops before calling Roblox (`ShopClient.lua:350`).
- **No Roblox calls for it.** The server skips `id = 0` when checking passes (`ShopServer.lua:248`), and a purchase can never match it (`ShopConfig.lua:168`).
- **The effect is read on the server only** (`ShopServer.lua:216-225`). The IPO window's x2 preview (`IpoClient.lua:83-90`) only displays it.
- **The sync script handles it.** `sync_monetization.py:8` creates items that still have `id = 0`.

## 7. Are all IPO numbers in IpoConfig?

**Result: yes.**

- **In IpoConfig (`IpoConfig.lua:17-75`):** stages, growth per IPO, multiplier, Shares formula, starting Cash, cooldown, and every perk's costs and effects.
- **Elsewhere, correctly:**
  - The Shareholder x2 is in ShopConfig. CLAUDE.md says pass effects belong there.
  - The 3 base incubators come from `CreatureConfig.Incubators`.
  - The IPO screen's maximum incubator count is worked out from IpoConfig (`EmployeeClient.lua:478`).
- **The only plain numbers in IpoServer and IpoClient** are UI timings: the pad cooldown of 3 s, the confirm timeout of 15 s and the label distance.

## 8. All findings, ranked

| # | Severity | Where | What breaks | Fix |
|---|---|---|---|---|
| F9 | **High** | `TycoonCore.lua:374`, `ShopServer.lua:307`, `PoachServer.lua:656` | Leaving while the save is still loading writes a save without `team`, `poach` and `ipo`: employees, HR and IPO progress are lost. Older than M4; M4 makes it worse. | Set `data.loaded` only after every `setupPlayer` has finished, inside `pcall`. Keep `gained` notes in `data.poach.gained` until resolved. |
| F1 | Medium | `TycoonCore.lua:248-250`, `:264`, `PoachServer.lua:628-637` | An IPO resets the HR level; ROADMAP says it's kept. | Remove the reset, update the 3 texts, consider a short Poach Shield after an IPO. |
| F2 | Medium | `TycoonCore.lua:203-211`, `EmployeeServer.lua:498-502` | Code that doesn't know a section deletes it: an old server wipes `ipo` and incubators 4 and 5 during the M4 rollout or a rollback. | Copy back unknown sections in `save()`. Publish M4 with **Shut down all servers**. |
| F3 | Low | `PoachServer.lua:466`, `:104-107`, `:615-626` | A Counter-Offer during the poacher's IPO save can wipe the payment the poacher should get. A victim can go public with an open Counter-Offer and lose the buy-back. | Refuse a Counter-Offer while the poacher isn't ready; count an open Counter-Offer in `isBusy`. |
| F4 | Low | `IpoClient.lua:594-614` | The confirm screen doesn't count the eggs that will be lost or warn about ready ones, and its Cash amount can be out of date. | Have the server send the egg counts, show a warning for ready eggs, refresh the Cash. |
| F5 | Low | `TycoonCore.lua:382-391` | Old saves get an uncapped valuation, so lots of Shares on the first IPO. | `math.min(legacyValuation, IpoConfig.ipoValuation(0))`. |
| F6 | Low | `PoachServer.lua:281-298`, `:615-626` | After a crash, an unfinished poach can refund Cash from before the IPO into the new run. | Accept it and list it in ROADMAP "Known low risks". |
| F7 | Low | `IpoServer.lua:235`, `:124-134`, `:119-121` | "Still loading" shows during an IPO; `addEarnings` has no NaN check (not reachable today); `isBusy` is unused. | Show "Your IPO is being filed", reject NaN and infinity, use or remove `isBusy`. |
| F10 | Low | no session lock (M9) | Leaving mid-IPO and joining another server fast can undo the IPO. Nothing is duplicated. | M9 session locking. |
| F8 | Balance | `IpoConfig.lua:25`, `:31` | Each run gets much longer (stages x38 by IPO 10, multiplier only x3.6). | Try 1.3 and 1; rerun `tools/economy_sim.py` with the real values. |

**Counts:** Critical 0 · High 1 · Medium 2 · Low 6 · plus 1 balance note.

## 9. Verdict

**Block the merge until F9, F1 and F2 are fixed.**

- They're all small changes in TycoonCore and PoachServer, which this branch already claims.
- **F9 is older than M4, but it should still be fixed here.** It's the only finding where an ordinary moment (leaving right after joining) destroys a save, and the IPO section is the most valuable part of the save.
- **F1 needs a decision either way.** Either the code keeps the HR level, or ROADMAP changes. Right now they disagree.
- **F2 only needs the copy-back code and the right publish button.**
- **The Low findings can go in this PR or the next one.** None of them can be triggered by a client, and the game isn't launched yet.

The server authority, the IPO lock, the atomic IPO save, the Shareholder placeholder and the config layout all hold up well.

## Coverage

| Area | Status |
|---|---|
| TycoonCore: save, load, `commitIpo`, legacy valuation, income loop | Done |
| IpoServer: Go Public, perks, pad, setup, serialize, Debug | Done |
| IpoConfig | Done |
| PoachServer: `isBusy`, Counter-Offer, transfer, reconcile, HR | Done |
| EmployeeServer: setup, serialize, hatching, Instant Hatch, release and add, IPO hooks | Done |
| ShopServer: setup, pass checks, receipts, Debug gate, Shares multiplier | Done |
| IpoClient, ShopClient (purchase prompts), EmployeeClient (perk display) | IPO-related parts |
| Server authority | Done (section 2) |
| Data integrity | Done (section 3). Checked by reading the code; no playtest, to keep the real DataStore save safe. |
| Reset scope | Done (section 4) |
| M2 eggs and M3 poaching | Done (section 5) |
| Monetization | Done (section 6) |
| IPO numbers in IpoConfig | Done (section 7) |
| Not covered | PoachClient, the full layout of IpoClient on a phone, `sync_monetization.py` beyond the `id = 0` rule |
