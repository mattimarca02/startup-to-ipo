# Pre-publish check 2 (after overhaul 2)

A read-only check of `main` at `ab0cba5` (after PRs #72, #73 and #74), done on 2026-10-19 by the owner session 3. No game script was changed. Open PRs #64, #75 and #76 were not part of it. Each of them runs the same suites.

**Verdict: nothing blocks the publish. There are two Medium points (section 3) and some Low ones.** The publish still needs **Shut down all servers**, because the `office` and `founder` sections are new (docs/PUBLISH_RULES.md 2e and 2f).

## 1. Old saves (no `office`, no `founder` section)

**Run end to end with fakes:** `tools/prepublish2_oldsave.py` runs the real `TycoonCore.lua` in lobby_test's fake Roblox, with one extra scenario. Result: 100 passed, 0 failed (the 90 existing checks plus 10 new ones). It loads two saves:
- A save from before overhaul 2: Cash, owned items, shop, team, ipo (1 IPO, valuation 7,000), onboarding, plus an unknown section from a newer version.
- An M4-era save: only `cash`, `owned` and `lastSeen`.

| Check | Result |
|---|---|
| Both saves load (`loaded`, `ready`); Cash and items are kept | OK |
| No `office` section gives 4 bought desks (the old 5 slots), for both saves | OK |
| FounderServer sets up with no saved section | OK |
| The leave save writes `office = { v = 1, desks = 4 }` | OK |
| The unknown section is written back unchanged; every old section is still there | OK |
| No error in the server | OK |

**Already covered by the suites, with the real modules:**
- `tools/office_test.py`:
  - A save with no `office` gets 4 desks. A saved count loads, a bad one gets 0, a count over four is clamped, and unknown fields and a newer `v` are kept.
  - The one-time building move: a save at the old Series A keeps the Big Office it saw, the move never runs twice, the old stage counts IPOs, and a locked pokedex is never changed.
- `tools/founder_test.py`:
  - A new player gets no `founder` section.
  - A saved section keeps `run`, `pitched`, `dinnerDay` and unknown fields.
  - Bad entries are skipped with a warning, and an older run starts the pitches again.
  - A section that is not a table is skipped and not written.

**Worth knowing:**
- A save written less than about 7 seconds before the join waits for TycoonCore's re-read of a recent save before it loads. This is by design, and the fake needed a longer wait for it.
- An old save at the old Series A (valuation 7,000) keeps the Big Office (building 3). Its funding stage, though, is still the Garage under the new economy (Seed is at $30K). So it can buy items only from the stages it has reached. This is the plan's rule (1.3: never less than it had), not a bug.

## 2. Part counts

Measured in a Studio playtest (each building built once from the real `PlotBuilding` with the kit) and by `tools/building_test.py`:

| What | Parts | Budget |
|---|---|---|
| Garage building | 88 | 180 |
| Small Office | 89 | 180 |
| Big Office | 150 | 180 |
| Small Corporate | 143 | 180 |
| Big Corporate | 159 | 180 |
| HQ Tower | 173 in Studio, 174 in the test | 180 |
| Biggest room with every item | 403 | 420 |
| World model (plaza, ring, arch) | 502 in Studio; the arch is 50 | 520 for the ring |
| VIP Lounge with its inside | 53 | — |
| **Six garages at their biggest stage plus the plaza** | **3,994** | **4,000** |

- With one player in Studio before the claim, the Workspace holds 1,955 parts.
- Each building has 1 light, the world has 4 to 6 lights, and each room has at most 3.
- PR #76 (the smooth arch) keeps the arch at 50 parts, and PR #75 adds no parts.
- **The phone's frame rate was not measured.** Until it is, no budget should rise.

## 3. Server-side checks

This section was read from the code on `main`.

### Calls (`TaskServer`, `TaskAction`)
**Checks found:**
- It checks the engine switch, `data.tasks` and `data.ready` (TaskServer.lua:525-532).
- It refuses a non-text action or an unknown one.
- Each player has a rate-limit bucket: 8 burst, 8 per second.
- The call number must be a whole number from 1 to 2^31, so NaN, infinity, negatives, fractions and tables are refused.
- The answer is checked and closed without yielding, so a double tap finds the call already gone.
- At most 40 answers a minute, with a cooldown per row.
- The server's clock decides the deadline and the reaction time. An answer under 0.25 s is flagged and pays 0, and the flags survive a rejoin for an hour.
- It refuses answers while an IPO is being saved.
- Pay goes through the bank, then the daily cap, then `core.addEarnings`, with amounts from the config only.
- The tick runs in a `pcall` for each player.

### The desk board's Answer (`FounderClient`)
**Checks found:**
- It sends the same `TaskAction("Answer", id)` as the phone tray, and Decline sends `"Skip"`. The server grades the call at once.
- The 3 s sit is display only.

### The VIP Investor dinner (`FounderServer`)
**Checks found:**
- On Start, the server checks:
  - the real VIP pass (`ShopServer.isVip`; the simulated passes exist only in Studio's Debug tab);
  - that `dinnerDay` is before today;
  - the reach to the table (12 studs), measured on the server.
- Only one activity runs at a time, and nothing starts while an IPO is saving.
- The pay is a `"bonus"`: outside the bank, but inside the daily cap, and clamped to 600 s of Income.

### Founder activities (`"Start"`, `"Pick n"`, `"Cancel"`)
**Checks found:**
- It checks `Enabled`, `data.founder` and `data.ready`.
- Each player has a rate-limit bucket: 6 burst, 4 per second.
- Start needs a string. A Pick must be a finite whole number, and each activity checks its own range.
- Only one activity runs at a time. Cooldowns run on the server's clock (sprint 180 s, brainstorm 300 s), and reach is measured on the server.
- The code lines and the right answers live only on the server. A sprint pick under 0.4 s or after the deadline counts as wrong.
- Every reward goes through `TaskServer.payReward`. The bug's penalty never takes Cash below $0 and never lowers the valuation.
- A pitch is marked once per round, and the marks reset with the IPO count.

### Reset my save
**Checks found:**
- It is registered only inside `RunService:IsStudio()`.
- The `ShopDebug` remote exists only with `IsStudio()` and `DebugInStudio`, and the handler checks both again, plus the arguments and `data.ready`.
- Arm and Confirm must come within 15 s, and a double Confirm is refused.
- `data.loaded` is turned off first. `RemoveAsync` runs in a `pcall` on the caller's own key, and a failure turns `loaded` back on. Then the player is kicked.

## 4. Risks

**High:** none found.

**Medium:**
1. **Founder cooldowns and the bug alarm live only in memory.** A rejoin makes the sprint and the brainstorm ready again and starts a fresh alarm timer. The damage is limited: a same-day rejoin starts with an empty reward bank, so past the bank, rewards pay only the capped share.
2. **Pitch and dinner Picks have no minimum reaction time** (the sprint has 0.4 s). The good answer is also the sensible-sounding option, so a script can answer every question in milliseconds. The pay is still once per round for the pitch and once a day for the dinner.

**Low:**
- `("Pause", false)` skips the TaskAction rate limit. Each call is cheap.
- Calls and the desk board have no reach check. This is by design, because the phone tray answers from anywhere.
- The dinner's `dinnerDay` is the day it ends. A dinner started just before 08:00 UTC uses up the next day's dinner. This only hurts the player.
- Pick and Cancel are not blocked while an IPO is saving. A pitch answered in that window pays Cash the valuation ignores, or marks the old round. This only hurts the player.
- Cancel on a bug avoids the penalty, so a failure can always be dodged. This is by design.
- The brainstorm's Pick doesn't check its own 60 s deadline. The 0.5 s tick does, so the most it can be late is one tick.
- The FounderAction handler has no `pcall`. If it errors after an activity ends, the cooldown is set but nothing is paid. Only the caller sees the error.
- The reach checks trust the character's position, which a teleport exploit can fake. This is a general Roblox limit.
- **In Studio only:**
  - An autosave that is already waiting when Reset is confirmed can write the erased save back.
  - A leave during the reset's wait plus a failed `RemoveAsync` loses that session.
  - The Debug remote has no rate limit.
- **Settings:** Max Players is still 60 in Studio. Set it to 6 in Creator Hub (the server log reminds you on every start).

None of the Medium points lets a player earn without limit. Both are worth a small PR after the publish: save the cooldowns in the `founder` section, and add a 0.4 s floor to pitch and dinner picks.
