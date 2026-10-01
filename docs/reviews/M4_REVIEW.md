# M4 review: IPO rebirth

PR #6, branch `milestone-4-ipo`. Code reviewed at commit `e9be034`. All `file:line` references point at that commit.

**Status: in progress.** Sections are added and committed one at a time, so nothing is lost if the review stops halfway.

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
- **What breaks:** the screen only says "eggs in incubators". Eggs that are ready to hatch are wiped without a specific warning, including eggs made ready with **Instant Hatch** (a Robux product).
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

## Coverage so far

| Area | Status |
|---|---|
| TycoonCore: save, load, `commitIpo`, legacy valuation, income loop | Read in full |
| IpoServer: Go Public, perks, pad, setup, serialize, Debug | Read in full |
| IpoConfig | Read in full |
| PoachServer: `isBusy`, Counter-Offer, transfer, reconcile, HR | Read in full |
| EmployeeServer: setup, serialize, `clearIncubators`, `refreshCapacity` | Read |
| IpoClient: confirm screen, IPO tab texts, "Done" banner | Read |
| Server authority (every IPO remote action, faking or skipping requirements) | **Left** |
| Data integrity: rejoin mid-IPO, shutdown during an IPO, double-firing, old and corrupted saves | **Left** (first-pass notes only) |
| Reset scope (exactly what's wiped and kept) | **Left** (partly covered by F1) |
| M2 eggs (EggsEnabled false, perks, Instant Hatch) and M3 poaching | **Left** (partly covered by F3, F4, F6) |
| Monetization: Shareholder pass placeholder (ShopConfig, ShopServer, ShopClient) | **Left** |
| All IPO numbers in IpoConfig (sweep for hard-coded values) | **Left** |
