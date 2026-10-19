# Overhaul 2 report

The owner's feedback of 2026-10-19 (points 1 to 15) and his addendum (points 16 to 18), built in six stacked pull requests by the owner session 2 (Claude Code in VS Code, with the Studio MCP on the place *Build your Startup!*, PlaceId 86395856666175). The plan is in docs/OVERHAUL2_PLAN.md.

**Merge the PRs in order: #65, #66, #67, #68, #69, #70, then this one (#71).** Each PR is based on the one before it. Nothing was published, and no Creator Hub setting was changed.

## Done, by the owner's points

| Point | What | PR |
|---|---|---|
| 1 | A Roman triumphal arch at the plaza's gate. It is white marble, about 42 wide and 34 high, with a 12 x 20 archway, side passages, eight columns, the entablature, and BUILD YOUR STARTUP carved in Garamond on the attic. Only the piers are solid. | #69 |
| 2 | The fountain: a basin with a moulded rim and two tiers of bowls with water. The client adds a splash and a soft water sound. Benches are at a character's scale (seat 2 high) and lamps are 12 high. | #69 |
| 3 | The join cinematic: a 7-second flight over the plaza that lands behind the character. It plays once per session, a tap skips it, and it runs on the client only. | #69 |
| 4 | The FREE sign is now a board on the claim post with a SurfaceGui on both faces. Nothing in the lobby is AlwaysOnTop any more. | #69 |
| 5 | An invisible solid box for each piece of furniture: workstations, chairs, stations, catalog items and the rooms' decor. Aisles, the lane and the spawn stay free. | #66 |
| 6 | **Calls are live.** While a call waits, a board over the founder desk offers Answer and Decline. Answer walks the founder to the desk and seats them for 3 seconds; the server grades the call at once. | #67 |
| 7 | The hatch reveal follows the creature's rarity, using a 3D egg. A Common takes about 1.3 s; a Legendary about 6 s, with rays, sparkles, a camera shake and a built-in sound. The eggs in the incubators have bands and spots. | #68 |
| 8 | Hires sit at their workstation and type. A new hire walks in along the aisles. | #66 |
| 9 | Workstations are bought: 1 free, then 4 to buy. The Extra Employee Slots pass still gives exactly 3 more. | #65, #66 |
| 10 | The green "Next: ..." sign is gone. In its place is a chalk blackboard over the entrance lane, facing the spawn, with the next goals and the cheapest item. | #67 |
| 11 | The building follows the building bought, never the valuation, so you can no longer jump from the Garage to Big Corporate. | #65 |
| 12 | Buildings are bought in SHOP > Office. Each funding round unlocks the next building. | #65 |
| 13 | The new economy: six stages including Series C, the HQ Tower, the retune, and offline pay and Cash packs counting only 10% toward the valuation. | #65 |
| 14 | Four founder activities. See below. | #67 |
| 15 | Facade and room materials, the HQ Tower's fins, and the kit's RenderFidelity checked. | #70 |
| 16 | 63 office items. Each appears in the room of its stage. | #65, #66 |
| 17 | Direct hires for Cash: a fixed creature for a fixed price, with no roll. | #65 |
| 18 | The VIP Lounge's inside: sofas, a bar, lamps, and a showcase with the richest VIP's rarest employee and valuation. Plus the Investor dinner. | #69 |

The four founder activities (point 14):
- **Coding sprint** at the founder desk. You find the buggy line in 5 rounds. It pays 20 + 3 s of Income per right line, then waits 3 minutes.
- **Production bug** at the Server Rack. An alarm rings every 4 to 7 minutes. You press 4 fixes in order within 20 s. A fix pays 25 s of Income. A wrong press costs 10 s of Income, but never more than your Cash and never from the valuation. Ignoring the alarm costs nothing.
- **Brainstorm** at the blackboard. You pick one of three boosts.
- **Investor pitch** at the founder desk, once per funding round. It has 3 questions, and each good answer pays 40 s of Income.

Also done (the owner's requests during the work):
- **Reset my save.** Studio only, in two steps, in the Debug tab (#66). It was not pressed: it is the owner's button.
- **Studio Debug buttons** for every new system: the founder activities, the pitch, the dinner, and the bug alarm.

## Not done, or not checked

- **2-player tests (Test > Clients and Servers).** The MCP drives only one client. Phase 5 changed the plaza and the claim post, so the owner should run this test before publishing.
- **Phone tests (Test > Device) and phone FPS.** The MCP's Studio client is throttled to about 15 FPS when Studio is in the background, so its numbers mean nothing. Steps are in docs/STUDIO_SYNC_BATCH.md, Batch 13.
- **Looks checked by eye.** The MCP's screen captures are unreliable. Every look was checked from data (sizes, positions, part counts, the room and world checks), not with eyes: the arch, the fountain, the reveal, the blackboard and the cinematic.
- **A real click on the desk board's Answer.** The MCP cannot press a BillboardGui button. The code path was read and the board's state was checked.
- **"No dead time over 2 minutes in the first hour"** was checked by reasoning, not with the sim. Calls ring every 20 to 40 s from the free Desk, the first item. The sprint and the brainstorm are always there after their wait.
- **The arch's curve is stepped.** World parts may only turn in quarter turns, so the curve is made of steps.
- **The fountain's sound** is the built-in `impact_water.mp3`, looped slowly. There is no other built-in water sound.
- **The plan put the blackboard on the back wall.** Every room's back wall has its door, windows or decor, so it hangs where the old sign stood: the one spot that is free in all six rooms.
- **Gate G1** (task engine PR 1) was not measured. The owner's brief asked to turn calls on, and the stats line stays, so f can still be read live.

## Rule changes (each in its PR and in CLAUDE.md, with the owner's written OK for look, layout, stage-count and economy pins)

- **Rooms:**
  - At most 420 parts per room; it was 260.
  - The Garage's fingerprint changed: the desk is a crate, an upturned bucket and a laptop.
  - Hires sit at their workstation; they no longer wander.
  - The Seed room's walls are Concrete.
- **Buildings and plaza:**
  - Six garages at their biggest stage plus the plaza must stay under 4,000 parts; it was 3,200. They are at 3,994.
  - The ring world's budget is 520; it was 480.
  - The world may use Marble and Garamond.
  - Small Office walls are Concrete, Big Office walls are Brick, and Small Corporate frames are Metal.
- **Calls:**
  - `TaskConfig.StudioOnly` is false.
  - The daily cap is 3 engaged hours at full value, then 25%.
  - A rejoin on a day the player was already engaged starts with an empty reward bank.
  - The call goals are shown on live servers.
  - TaskServer reads `data.owned` twice: for the unlock, and for the items' calls effect.
- **The garage's signs:**
  - The next-upgrade sign became the blackboard; the frame tests at four turns now check the blackboard.
  - The FREE sign became a board; the lobby runtime test checks the board.
  - LobbyClient's marker is no longer AlwaysOnTop.
- **Save and setup:**
  - `KNOWN_SECTIONS` gains `office` and `founder`.
  - `save()` waits for `data.office` and `data.founder`.
  - FounderServer is set up after the marked load block, next to the `office` section.
- **CLAIMLOAD and tests:**
  - The CLAIMLOAD block is still byte-identical to main at 99eed7b. TycoonCore's edits outside it are listed in `tools/lobby_test.py`: `O1_EDITS`, `O2_EDITS`, `O3_EDITS` and `O5_EDITS`.
  - No test that protects saves, purchases, server authority or the claim was weakened.
- **New test suites:**
  - `tools/office_test.py` (phases 1 and 2).
  - `tools/founder_test.py` (phases 3 and 5).
  - `tools/egg_test.py` (phase 4).
  - `tools/plaza_test.py` (phase 5).

## The economy, before and after (docs/ECONOMY.md section 10; `tools/economy_sim.py --o2`)

| | Before overhaul 2 | After |
|---|---|---|
| Funding stages | 5 (Garage, Seed, Series A, Series B, IPO-ready) | 6 (Series C added) |
| Seed at | $1,800 of valuation | $30K |
| IPO-ready at | $202K (first run) | $1B |
| Growth per IPO | x2.5 | x1.1 |
| First run, perfect active player | about 12 minutes | Seed about 55 min, IPO about 18.4 h |
| Building | followed the valuation (offline pay could jump stages) | bought in the shop, one step at a time |
| Offline pay and Cash packs | 100% toward the valuation | paid in full, 10% toward the valuation |
| Shares per IPO | 10, +80% per IPO | 40, +50% per IPO |
| Catalog | 6 upgrades | 63 items (the six old names kept) |
| Team size | 5 base slots | 1 free + 4 bought workstations, + 3 with the pass (same value), + perks, at most 11 |
| Task rewards | Studio only | live, with a 3 h/day full-value cap, a reward bank that a same-day rejoin doesn't refill, and the founder activities through the same bank |

## Save sections

| Section | New in | Shape | Notes |
|---|---|---|---|
| `office` | phase 1 (#65) | `{ v = 1, desks }` | Workstations bought, kept through an IPO. A save without it is from before overhaul 2 and gets 4 desks (the old 5 slots). |
| `founder` | phase 3 (#67) | `{ v = 1, run, pitched = { [stage] = true }, dinnerDay }` | Pitches done this run and the day of the last VIP dinner. Unknown fields are written back. Nil until there is something to keep. |
| `tasks` | (PR 1, existing) | unchanged | Now written for live players too, because calls are live. |
| `owned` | (existing list) | more names | The catalog's item names. Every version back to M4 keeps any name there. |
| `pokedex.active.building` | (existing field) | 1 to 6 | The building bought. |

The DataStore name and key did not change. Every new section is rule A10: in `KNOWN_SECTIONS`, optional on load, and keeps unknown fields. **Publishing overhaul 2 needs Shut down all servers** (docs/PUBLISH_RULES.md 2e and 2f).

## Frame rate

- **Measured, with one player in Studio:**
  - The server steps at 60.1 Hz.
  - The workspace holds about 2,300 parts.
  - The Studio client rate (about 15 FPS) is throttled because Studio is in the background, so it is not a measurement.
- **Part counts at the biggest stage:**
  - A room with all its items: 403 parts (budget 420).
  - The HQ Tower building: 174 parts with the kit (budget 180).
  - The ring world: 502 parts (budget 520).
  - The lounge's inside: 42 parts.
  - Six garages plus the plaza: 3,994 of 4,000.
- **Lights:**
  - Each room has at most 3 PointLights.
  - Each building has 1.
  - The world has 6.
  - The lounge has 4.
- **Still to measure on a real phone:** the frame rate, by the owner, in a full server (Batch 13). Until then, no part budget should rise again.

## Publish checklist (only when the owner decides)

1. Merge #65, #66, #67, #68, #69, #70, then #71, in that order, into `main`.
2. Studio already matches the last branch (the hashes in Batches 8 to 13). After the merges, compare once more: the hashes must not change.
3. In Creator Hub, set Max Players = 6 (Studio still says 60).
4. Run the tests by hand:
   - 2 players (Test > Clients and Servers): the claim, the plaza, the FREE board, the lounge.
   - Test > Device at 320x568 and 667x375: the activity window, the call board, the blackboard.
   - Phone FPS.
5. Press Reset my save if you want a new player's start. It is your choice, and it is Studio only.
6. **File > Save to Roblox**, then commit every draft (View > Drafts).
7. Creator Hub: **Shut down all servers**, then File > Publish to Roblox, then **Shut down all servers** again. Never Migrate.
8. Write down the new version in Version History. Join, and check the server log: no "Could not set up", no "Keeping a part of ... save".
