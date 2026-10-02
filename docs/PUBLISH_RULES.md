# Publish rules: Build your Startup!

The rules for every publish of place `86395856666175` (universe `10768772528`), from launch on. They come from review findings FR-15, FR-18 and FR-19 in docs/reviews/FULL_REVIEW.md (section 9). This file replaces the "Order of publishing day" part of the old pre-publish checklist (docs/PREPUBLISH.md, which stays on the `claude/prepublish-checklist` branch). The other checklist items (account, store page, tests by hand) still apply.

## 1. Server size: Max Players = 6 (set by hand)

The game has 6 plots (`MAX_PLOTS = 6` in TycoonCore) and kicks the 7th player with "This server is full". Roblox fills servers up to the place's Max Players, so it must be **6**:

- Creator Hub > Creations > Build your Startup! > **Places** > the place > **Max Players: 6** (or Studio: **Game Settings > Places**). Save.
- Check it again after every publish: the setting belongs to the place, not to the scripts.
- If the plot count ever changes, change Max Players in the same release.

## 2. Rollback floor: never restore a version older than M4

Code older than M4 (`2f998a7`, the "KNOWN_SECTIONS" rule) **deletes every save section it doesn't know**. A player who joins such a version loses `ipo` (IPO count, Shares, perks, best valuation), `daily` (streak; Day 1 becomes claimable again) and `onboarding`, and the eggs in incubators 4 and 5. It's permanent: back on a newer version, the IPO section is rebuilt from a capped guess and the Shares and perks are gone.

M4 has never been published, so **the version live today is older than M4, and so is every version before launch.** The rollback floor is therefore the **launch version** (`V_launch` below):

- **Allowed:** Version History > Restore a version **at or after `V_launch`**, then **Shut down all servers**.
- **Never:** restore `V_old` or anything before `V_launch`. Fix forward instead.
- Write both numbers here when you publish:
  - `V_old` (live before launch, below the floor): ______
  - `V_launch` (the floor): ______
- A rollback to an allowed version is still lossless only if every update follows CLAUDE.md's rule that new saved data gets its own top-level section (A10).
- The newest section is `fixedHires` (FR-13, D9 option B: the fixed hire order's counter per egg, only written once a restricted player has hatched an egg). Code from M4 on keeps it unchanged if it doesn't know it. But a version without D9 rolls eggs randomly for players in restricted regions again (Paid Random Items policy): once D9 is live, never restore a version without it.
- **Perk levels 6 and up (D1, the 1,770-Share shop):** a rollback to a version with the shorter shop caps every perk level 6+ back to 5, and the Shares spent on those levels are lost (not refunded). It is a one-way change, forward only. Same as docs/D1_SHOP_OPTIONS.md (Rollback row).
- If saves were already damaged: Roblox keeps older versions of each DataStore key for a limited time (about 30 days); one player's save can be restored by hand from a version. Slow and manual.

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
1. All blockers done; `prepublish-fixes` and the fixes merged into `main` through a PR; every claim in CONTRIBUTING.md released.
2. Studio matches `main` exactly: compare every script (read only, Studio MCP or by hand). Commit all drafts.
3. `python3 tools/daily_test.py` passes ("N passed, 0 failed" on every line).
4. In Creator Hub, open the place's **Version History** and write down the live version as `V_old` (section 2).
5. Settings that can't change later without side effects: **Max Players = 6**; `DailyConfig.ResetHourUtc` (must be decided before launch: decided 8 UTC, never change it after launch because it gives every player an extra claim; see section 3c); `ShopConfig.EggsEnabled`; the experience stays private.
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
