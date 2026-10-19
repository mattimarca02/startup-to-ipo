# Publish rules: Build your Startup!

The rules for every publish of place `86395856666175` (universe `10768772528`), from launch on. They come from review findings FR-15, FR-18 and FR-19 in docs/reviews/FULL_REVIEW.md (section 9). This file replaces the "Order of publishing day" part of the old pre-publish checklist (docs/PREPUBLISH.md, which stays on the `claude/prepublish-checklist` branch). The other checklist items (account, store page, tests by hand) still apply.

## 1. Server size: Max Players = 6 (set by hand)

The game has 6 garages (`MAX_PLOTS = 6` in TycoonCore, `#LobbyConfig.Garages`: **6 = the garage count**) and kicks a 7th player with "This server is full" (lobby L3: only when there are more players than garages; with the claim off a joiner waits up to 60 s for a garage that is closing). Roblox fills servers up to the place's Max Players, so it must be **6**. TycoonCore warns at startup when it is higher:

- Creator Hub > Creations > Build your Startup! > **Places** > the place > **Max Players: 6** (or Studio: **Game Settings > Places**). Save.
- Check it again after every publish: the setting belongs to the place, not to the scripts.
- If the plot count ever changes, change Max Players in the same release.
- Same tab, **Social Slots**: Roblox optimized; if live servers log cap kicks, switch to the option that fills to the maximum. Other places in the universe that players can reach get the same value (docs/LOBBY_GARAGE_PROPOSAL.md section 4.4).
- **The lobby (branch `lobby-all`):** no new save section and no rollback change. `LobbyConfig.ClaimEnabled` is **true in the repo since 2026-10-18** (owner decision 9 revised; before, it shipped false and nothing moved for live players). Turning it on in the live game is a publish with **Shut down all servers** (old servers keep the old flow until they restart), with the SpawnLocation moved to the plaza first (docs/STUDIO_SYNC_LOBBY.md, section "Lobby all" 10).

## 2. Rollback floor: never restore a version older than M4

Code older than M4 (`2f998a7`, the "KNOWN_SECTIONS" rule) **deletes every save section it doesn't know**. A player who joins such a version loses `ipo` (IPO count, Shares, perks, best valuation), `daily` (streak; Day 1 becomes claimable again) and `onboarding`, and the eggs in incubators 4 and 5. It's permanent: back on a newer version, the IPO section is rebuilt from a capped guess and the Shares and perks are gone.

M4 has never been published, so **the version live today is older than M4, and so is every version before launch.** The rollback floor is therefore the **launch version** (`V_launch` below):

- **Allowed:** Version History > Restore a version **at or after `V_launch`**, then **Shut down all servers**.
- **Never:** restore `V_old` or anything before `V_launch`. Fix forward instead.
- Write both numbers here when you publish:
  - `V_old` (live before launch, below the floor): ______
  - `V_launch` (the floor): ______
- A rollback to an allowed version is still lossless only if every update follows CLAUDE.md's rule that new saved data gets its own top-level section (A10).
- The newest section is `pokedex` (section 2d, customize PR 1: written for every player). The newest one written only once there is something to keep is `tasks` (section 2b, task engine PR 1). The newest *live* section is `fixedHires` (FR-13, D9 option B: the fixed hire order's counter per egg, only written once a restricted player has hatched an egg). Code from M4 on keeps it unchanged if it doesn't know it. But a version without D9 rolls eggs randomly for players in restricted regions again (Paid Random Items policy): once D9 is live, never restore a version without it.
- **Perk levels 6 and up (D1, the 1,770-Share shop):** a rollback to a version with the shorter shop caps every perk level 6+ back to 5, and the Shares spent on those levels are lost (not refunded). It is a one-way change, forward only. Same as docs/D1_SHOP_OPTIONS.md (Rollback row).
- If saves were already damaged: Roblox keeps older versions of each DataStore key for a limited time (about 30 days); one player's save can be restored by hand from a version. Slow and manual.

## 2b. The `tasks` save section (task engine, PR 1)

PR 1 (branch `pr1-task-engine`: `TaskConfig`, `TaskServer`, `TaskClient`) adds a **new top-level save section `tasks`** (rule A10), and it is in `KNOWN_SECTIONS`:

```lua
tasks = {
  sharesRun = number,       -- IPO count a pitch's Shares reward was last used for (later PRs; 0 now)
  done = number,            -- calls answered and graded by the server, ever
  bestChain = number,       -- longest chain of answered calls
  seen = { Call = true },   -- task keys the player has met
  engagedDay = number,      -- DailyConfig.dayNumber (the 08:00 UTC day) the counter below belongs to
  engagedSeconds = number,  -- engaged seconds on that day (PR 2 caps full-value time with it)
}
```

- **Needs "Shut down all servers"** (new section, same as `daily` and `onboarding`): an old server still running would drop it on its next save. Never Migrate.
- **Rollback floor stays `V_launch`.** From M4 on, older code keeps a section it doesn't know unchanged, so rolling back to a version without the task engine (but at or after `V_launch`) loses nothing: `tasks` stays frozen and works again when you go forward (a stale `engagedDay` is simply ignored). Code older than M4 deletes it, like every other section (section 2).
- **PR 1 runs only in Studio** (`TaskConfig.StudioOnly = true`): on a live server the engine builds no remotes, starts no loop and shows nothing, and a player gets **no `tasks` section at all** unless one is already in their save (it is written only once there is something to keep). The DataStore key is shared by Studio and live servers, so a save a developer made in Studio can carry a `tasks` section. It loads and saves back unchanged.
- **Do not set `StudioOnly = false` on its own.** Task Cash must not count 100% toward the IPO valuation before the economy core (PR 2: `addEarnings(kind)`, the 3 h/day full-value cap). PR 2 flips it, and PR 2 also needs "Shut down all servers" (new `away` section).
- Loading is defensive: a number that is NaN, infinite, negative or not whole is skipped with a warning (counts over their limit are clamped, `engagedSeconds` to one day), `seen` keeps at most 50 `{ key = true }` entries, a counter dated after today (even tomorrow) is rejected: the engaged day and seconds start again at today with 0 seconds, the other fields stay; an older day's seconds are ignored, and fields this version doesn't know are written back as they were. A bad `tasks` section never touches another section.

### Studio sync order for PR 1 (do this before pasting TycoonCore and ShopClient)

`TycoonCore` requires `TaskServer` with `WaitForChild` **and no timeout**, and `TaskServer` waits for `TaskConfig` the same way. If TycoonCore is pasted first, the server script hangs on "Infinite yield possible" and nobody can load a save. Create the three new scripts first, then paste the two changed ones:

1. `TaskConfig` (ModuleScript) in **ReplicatedStorage**.
2. `TaskServer` (ModuleScript) in **ServerScriptService**.
3. `TaskClient` (LocalScript) in **StarterPlayer > StarterPlayerScripts**.
4. Only then paste the new `TycoonCore` (Script, ServerScriptService) and `ShopClient` (LocalScript, StarterPlayerScripts). `ShopClient` waits 5 s for `TaskConfig` and then shows no Task Debug rows, so it never hangs, but it is still the last one to paste.

### Note for PR 2: a rejoin refills the reward budget

`run` (the per-session state in `TaskServer.newRun`, TaskServer.lua about line 92) is not saved, so a rejoin gives a full 60 s budget bank and clears the flag list (early answers, constant reaction). In PR 1 this is harmless (Studio only, no live Cash). **Fix it in PR 2** before `StudioOnly` goes off: save what must survive a rejoin (the bank and a flag cool-down) or start a rejoin with an empty bank.

## 2c. Plot visuals follow-up (branch `visuals-garage`): no new save section

The Office tab, the removal of the walk-on pads and the tidy layout add **no save section and no saved field**: what an upgrade needs (`owned`) and what an HR level needs (`poach.hrLevel`) were already saved, and the Office state the client shows (`Upgrade1` ... `Upgrade6` on the player) is rebuilt from `owned` on every join. So this change needs no extra publish step for the save and the rollback floor stays `V_launch`. (The earlier visuals-garage stage 1 also added no section.)

- **Two new request names, no new remote object except one:** `ShopRemotes.ShopAction` (a RemoteFunction made by `ShopServer.init`, on live servers too: `"Upgrades"` and `"BuyUpgrade"` with the upgrade's number) and `"BuyHr"` on the existing `PoachRemotes.PoachAction`. Publish with **Shut down all servers** as always (section 3): an old server has no `ShopAction`, and the new `ShopClient` then shows "The office upgrades aren't available right now" instead of the upgrades.
- **Studio sync order:** paste the server scripts first (`TycoonCore`, `ShopServer`, `PoachServer`, `IpoServer`, `OnboardingServer`, `EmployeeServer`, `PlotArt`, `PlotVisuals`), then the clients (`ShopClient`, `PoachClient`). An old client with the new server just has no Office tab; a new client with an old server shows the "not available" line (ShopClient) or "Unknown action" (PoachClient's Buy HR button).
- **A rollback to a version with the pads** keeps working: the saves are the same. The pads come back, and the Office tab is gone.
- Nothing is bought by touching the world any more (the three pads are gone). The one remaining `Touched` handler is the VIP Lounge door in ShopServer: it only opens Roblox's own purchase confirmation for the VIP pass.

## 2d. The `pokedex` save section (customize PR 1)

PR 1 of docs/CUSTOMIZE_PROPOSAL.md (branch `customize-pr1`: `CompanyServer`, `CompanyConfig`, `SectorConfig`) adds a **new top-level save section `pokedex`** (rule A10), in `KNOWN_SECTIONS` and in the save gate (`data.pokedex`). It is written for **every** player (a new founding if they had none), about 1 KB:

```lua
pokedex = {
  v = 1,            -- format version
  run = number,     -- the IPO count the active company belongs to
  active = { sector = "Software", picked, name, foundedAt, engaged, passSeconds, building, decor, objects, stored, told, rounds, sx },
  sectors = { [Software | Gaming | Fintech | Biotech] = { state, stamp, replays, firstAt, bestEngaged, card } },
  kept = {}, hall = {}, dust = 0,
  studio = true,    -- only if a Studio server saved it; never cleared
}
```

It changes **nothing players can see or earn**: the picker is off (`SectorConfig.PickerEnabled = false`), every company is a Software company, and nothing reads the section yet except its own rules. The three office requests (`CompanyRemotes.CompanyAction`: `"Place"`, `"Store"`, `"Sync"`) exist on live servers but refuse everything outside Studio (`CompanyConfig.Placement.StudioOnly = true`).

- **Needs "Shut down all servers"** (new section): an old server still running would drop it on its next save. Never Migrate.
- **Rollback floor stays `V_launch`.** From M4 on, older code keeps a section it doesn't know unchanged. Rolling back to a version without PR 1 (but at or after `V_launch`) loses nothing: `pokedex` stays frozen. If a player goes public on that older version, their `ipo.count` rises and `pokedex.run` doesn't; the next join with PR 1 runs the **run check**: the active company is completed (Bronze for its sector if it had none, a card) and a new one starts, once. So `run < count` means **only that**: an older version ran an IPO. An IPO done by PR 1's own code never leaves it behind: `commitIpo` writes `run = the new count` into the IPO's own save and moves the section in memory after the save worked (no stamp, no card and no sector completion until the IPO transform of PR 4; before that `run` simply follows the count). Code older than M4 deletes the section, like every other (section 2).
- **A newer version is never overwritten.** `v` rises only when a field changes meaning. A section with a higher `v` (or an active sector this version doesn't know, or one that can't be read) is written back exactly as it was, and that player can't go public on this version (the IPO is refused) or change their office. So after a rollback below a future format change nobody loses their Pokedex; they just wait for the newer version.
- **Studio and live share the save key** (section 2b): every Studio save sets `pokedex.studio = true`, for good, so a Studio save can never reach the leaderboard that comes in a later PR. Studio's Debug "IpoReset" lowers the IPO count: at the next join the run check sees `run > count`, sets `run` to the count, keeps the company, gives no stamp or card, and sets `studio`.
- **Loading is defensive:** a bad value is skipped with a warning (the rest of the section and every other section are untouched), and unknown fields, unknown item ids and stored values other than `true` are kept at every level and written back. A shape this version can't carry back (the placed items are not a plain list) keeps the whole section as it was, like a newer `v`.
- **Studio sync order** (docs/STUDIO_SYNC.md addendum (d)): create `SectorConfig`, then `CompanyConfig` (ReplicatedStorage), then `CompanyServer` (ServerScriptService), and only then paste the new `TycoonCore`. `TycoonCore` requires `CompanyServer` with `WaitForChild` and **no timeout**, and `CompanyServer` and `CompanyConfig` wait for their modules the same way: a missing one hangs the server script ("Infinite yield possible") and nobody can load a save.

## 2e. The `office` save section (overhaul 2, docs/OVERHAUL2_PLAN.md)

A new optional top-level section `office = { v = 1, desks }` (rule A10: in `KNOWN_SECTIONS`, read right after the CLAIMLOAD block, unknown fields written back). The catalog adds names to the existing `owned` list (every version back to M4 loads and writes back any name there) and the bought building lives in the existing `pokedex.active.building` with a new field `active.o2` (the pokedex loader keeps unknown fields). Publishing overhaul 2 needs **Shut down all servers**: an old server would not know the six stages, the catalog or the `office` section (it keeps the section, but its players would play the old economy beside the new one). The rollback floor stays M4. After a rollback to a version before overhaul 2, a player keeps the `office` section frozen (older code writes it back unchanged) and their catalog names in `owned`; their building would follow the old valuation rule again until overhaul 2 is back.

## 3. Old and new servers must never run at the same time (FR-19)

- Use **Shut down all servers** (the hard shutdown) for every publish. **Never "Migrate to latest update"**: it keeps old servers running while players move, and a player who goes from a new server to an old one loses the new sections (above).
- Before publishing, in Team Create: **View > Drafts**, commit every draft. An uncommitted draft is **not** published: the old script goes live.
- Nobody edits scripts during the publish.
- After publishing, join and check you're on the new code (for a release that changes the UI, the change is visible; for example the daily gift chip doesn't exist in old versions).

## 3b. Paid random items check (FR-13, D9 option B)

- Every join asks Roblox's `PolicyService` whether paid random items are restricted for the player (UK, Australia, Brazil, Belgium, the Netherlands at the time of writing). Restricted players get a fixed hire order instead of a random roll and no Luck Boost; everything else stays on sale.
- The check is **fail closed**: if Roblox errors, gives a bad answer or doesn't answer within 10 s (`ShopConfig.PolicyCheck`), the player is treated as restricted for that session. A normal player then gets one session of fixed-order hires (same odds) and their Luck Boost is kept aside, not lost.
- Not saved: it is asked again on every join, so a region change shows up on the next join.
- In the server log (F9 > Server), "Policy check ... failed" or "... is slow" now and then is normal; many of them mean Roblox's policy service is having trouble (players get fixed hires until it recovers).

## 3c. Daily reset hour (D3): 8 UTC, never change it

`DailyConfig.ResetHourUtc` must be decided before launch: **decided 8 UTC, never change it after launch because it gives every player an extra claim.** The day number is `floor((os.time() - ResetHourUtc * 3600) / 86400)` and `lastClaimDay` is saved as that number, so every save is tied to the hour it was made under.

- **Later hour (for example 8 to 12):** a player who claimed this morning waits a few hours longer. No extra claim.
- **Earlier hour (for example 8 to 0):** the hours between the two resets count as a new day, so everyone who already claimed can claim again. Each player gets one extra reward, once.
- Checked for the switch from 0 to 8 (no live players, so no migration needed): an old save with `lastClaimDay` made under hour 0 loads clean, is never clamped or warned about, and never gets an extra claim. At worst it waits until 08:00 UTC instead of 00:00. Test data claimed between 00:00 and 08:00 UTC just waits for the next 08:00 UTC; a player coming back between 00:00 and 08:00 UTC counts one missed day less, so the grace is slightly kinder, never harsher. Nothing breaks, so dev saves need no reset for this.

## 4. Publish order (place with no live players: the launch)

**Before publishing day**
1. All blockers done; `prepublish-fixes` and the fixes merged into `main` through a PR; every claim in docs/lanes/claims.md released.
2. Studio matches `main` exactly: compare every script (read only, Studio MCP or by hand). Commit all drafts.
3. `python3 tools/daily_test.py` passes ("N passed, 0 failed" on every line).
4. In Creator Hub, open the place's **Version History** and write down the live version as `V_old` (section 2).
5. Settings that can't change later without side effects: `TaskConfig.StudioOnly = true` until PR 2 (section 2b); **Max Players = 6**; `DailyConfig.ResetHourUtc` (must be decided before launch: decided 8 UTC, never change it after launch because it gives every player an extra claim; see section 3c); `ShopConfig.EggsEnabled`; the experience stays private.
6. Re-read Roblox's current Paid Random Items policy page (https://create.roblox.com/docs/production/monetization/paid-random-items) and the DevForum clarification linked in docs/D9_POLICY_OPTIONS.md. Write down the date you read it and the list of restricted regions it names: ______ (date), ______ (regions). If the rules changed (a new treatment required, Cash multiplier passes counted as paid, odds rules), stop and update D9 before publishing.

**Publishing day**
7. Creator Hub > the experience > the place's menu > **Shut down all servers** (even if you think none is running).
8. Studio: **File > Publish to Roblox**.
9. Right away: **Shut down all servers** again. Never Migrate.
10. Version History: write down the new version as `V_launch` (section 2). It's the rollback floor.
11. Join the private game with a second account. Server log (F9 > Server): no "DataStore unavailable", no "Keeping a part of ... save this version doesn't know", no "Could not set up", no "Policy check ... failed". Rejoin: IPO count, Shares, perks, daily streak and onboarding state are still there. Outside the restricted regions the Eggs tab shows each hire's odds and the shop shows Luck Boost (with `EggsEnabled` on); "Next hire from this egg" there means the policy check failed (section 3b).
12. Real purchases with the second account: one Cash pack, one pass, a Poach Shield; rejoin; nothing doubled, nothing missing.
13. Reset dev saves only with `RemoveAsync` on a written list of the dev UserIds, never a loop over unknown keys. Then the store page and the public switch.

## 5. Every later update

- If it changes the save: same order as above (steps 2-3, 7-11), hard shutdown only.
- If it doesn't: a hard shutdown is still the safe default; Migrate only for an update that touches no saved data and no remote, and never for one that adds a save section.
- Never restore below `V_launch`.
