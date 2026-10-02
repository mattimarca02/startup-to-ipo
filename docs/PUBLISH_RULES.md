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
- If saves were already damaged: Roblox keeps older versions of each DataStore key for a limited time (about 30 days); one player's save can be restored by hand from a version. Slow and manual.

## 3. Old and new servers must never run at the same time (FR-19)

- Use **Shut down all servers** (the hard shutdown) for every publish. **Never "Migrate to latest update"**: it keeps old servers running while players move, and a player who goes from a new server to an old one loses the new sections (above).
- Before publishing, in Team Create: **View > Drafts**, commit every draft. An uncommitted draft is **not** published: the old script goes live.
- Nobody edits scripts during the publish.
- After publishing, join and check you're on the new code (for a release that changes the UI, the change is visible; for example the daily gift chip doesn't exist in old versions).

## 4. Publish order (place with no live players: the launch)

**Before publishing day**
1. All blockers done; `prepublish-fixes` and the fixes merged into `main` through a PR; every claim in CONTRIBUTING.md released.
2. Studio matches `main` exactly: compare every script (read only, Studio MCP or by hand). Commit all drafts.
3. `python3 tools/daily_test.py` passes ("N passed, 0 failed" on every line).
4. In Creator Hub, open the place's **Version History** and write down the live version as `V_old` (section 2).
5. Settings that can't change later without side effects: **Max Players = 6**; `DailyConfig.ResetHourUtc` (moving it earlier later gives everyone an extra claim); `ShopConfig.EggsEnabled`; the experience stays private.

**Publishing day**
6. Creator Hub > the experience > the place's menu > **Shut down all servers** (even if you think none is running).
7. Studio: **File > Publish to Roblox**.
8. Right away: **Shut down all servers** again. Never Migrate.
9. Version History: write down the new version as `V_launch` (section 2). It's the rollback floor.
10. Join the private game with a second account. Server log (F9 > Server): no "DataStore unavailable", no "Keeping a part of ... save this version doesn't know", no "Could not set up". Rejoin: IPO count, Shares, perks, daily streak and onboarding state are still there.
11. Real purchases with the second account: one Cash pack, one pass, a Poach Shield; rejoin; nothing doubled, nothing missing.
12. Reset dev saves only with `RemoveAsync` on a written list of the dev UserIds, never a loop over unknown keys. Then the store page and the public switch.

## 5. Every later update

- If it changes the save: same order as above (steps 2-3, 6-10), hard shutdown only.
- If it doesn't: a hard shutdown is still the safe default; Migrate only for an update that touches no saved data and no remote, and never for one that adds a save section.
- Never restore below `V_launch`.
