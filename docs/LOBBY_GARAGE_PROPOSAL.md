# Lobby and garages proposal: one plaza, six garages you walk to and claim

Design only (2026-10-15, branch `lobby-garage`, from `main` `99eed7b`). No code, no `.lua` edit, nothing in Studio. Line numbers are `main` `99eed7b` unless a branch is named. **(unverified)** marks what I could not check from the repo.

**Owner decisions (fixed):** (1) one common server; a player spawns in the shared plaza, never at a garage, and there is no teleport to another place; (2) garages stand around the plaza, a player walks to a free one and claims it, and an empty garage starts from zero; (3) a returning player gets their saved company back in whichever garage they claim, because the company lives in the save, not in the slot; (4) the garage is a real, closed building with a complete interior, using the building-pass work if it fits.

Words used here: a **garage** is one of the six lots (the code says plot or slot); **claim** means "this garage is mine for this session".

## 0. The short version

On join the server does nothing with garages. Each free garage has a **"Claim garage" prompt** at its door. The server checks the request, then runs **today's loading code, unchanged, with that slot**: loading, setup, offline earnings and `data.ready` move from "on join" to "on claim". Leaving works as today. The save format does not change: the slot was never saved (TycoonCore.lua:422-435). Six garages form a horseshoe around a 180 x 180 plaza, open on the VIP Lounge side; they face the plaza, so the code learns quarter turns. The closed building comes from `building-pass`. Max Players stays **6**. Five pull requests, the first with no visible change.

## 1. From join to a claimed garage

### 1.1 Today

`onPlayerAdded` (TycoonCore.lua:734) takes the first free slot in `plotOwners` (:735-741), kicks a 7th player with "This server is full" (:742-744) and marks the slot taken (:746). It makes `leaderstats` (:748-758), the folder and `Floor` (:760-768), reads the save (:774; a failed read kicks, :776-782; a fresh save is read again after 7 s, :786-794), sets up every module in one `pcall` (:796-832), turns saving on (`data.loaded`, :839), builds the room (:842), pays offline earnings (:850-860), calls `refreshSign` (:862) and sets `data.ready = true` (:863). Only then does `teleportToPlot` (:725-732) move the character in, on every spawn (:865-870). On leave, `saveOnLeave` runs first and the slot is freed after it (:880-888), so the slot stays taken while the save runs (finding FR-3, docs/reviews/FULL_REVIEW.md:171).

### 1.2 The new flow

**Join.** `onPlayerAdded` records the player as "in the plaza" and stops: no slot, no `leaderstats`, no folder, no save read, no teleport. The character appears on the SpawnLocation, moved by hand to the plaza center (section 4). `playerData[player]` stays empty, and every server path already refuses a player with no data: EmployeeServer.lua:485-486, IpoServer.lua:267-268, PoachServer.lua:70, TaskServer.lua:504-507, CompanyServer.lua:74-76, DailyServer.lua:219, and the Office buy in TycoonCore.lua:274-278. No module needs a new guard.

**What marks a garage free.** `plotOwners[slot]` (TycoonCore.lua:88) stays the only truth, on the server. A garage has four states: **Free** (`nil`, claimable), **Moving in** (taken, owner's save loading), **Taken** (owner loaded) and **Closing** (owner left, leave save still running). The server copies the state to two attributes on the garage model (`State`, `OwnerName`) for display only; nothing reads them back.

**The claim.** A Free garage has a ProximityPrompt "Claim garage" on a post beside its door (hold 0.5 s, 10 studs). It is not a `Touched` handler, so CLAUDE.md:45 and tools/daily_test.py:7028 ("the only Touched handler is the VIP Lounge door") stay true; the incubators use prompts the same way (EmployeeServer.lua:531-543). When it fires, the server checks, in one block **with no yield between the check and the write** (the rule CLAUDE.md gives the daily claim):

1. the player has no garage and no claim loading (**one claim per player**);
2. the slot is a whole number from 1 to 6 and is Free;
3. the character's root part is within 14 studs of the door, measured on the server (Roblox may check prompt distance itself **(unverified)**; we check anyway);
4. at most one claim request per second per player;
5. `LobbyConfig.ClaimEnabled` is on (section 2.1).

If all pass: `plotOwners[slot] = player`, state Moving in, prompt off, load starts. Otherwise a short message through `ShopServer.notify` ("Taken by Ana, try another", "You already have a garage").

**Two claims of one garage at once.** Roblox runs the two prompt events on the server one after the other. Since nothing yields between "is it Free?" and "it's yours", the first wins and the second sees Taken. A test proves it with a fake scheduler (PR L3).

**Moving in.** The claim runs the old body of `onPlayerAdded` (:746-870) as `claimGarage(player, slot)`. The door sign says "Moving in...". A read normally takes about a second **(unverified)**; a save less than 75 s old waits 7 s more (:387-388); a read that keeps failing ends in today's kick, which frees the garage. Then the room of the player's stage appears with their props, employees and incubators, the building takes their stage, and the sign shows "Ana's Startup".

**The owner leaves.** `PlayerRemoving` (:880-888) and `saveOnLeave` (:528-544) stay: up to 3 tries, waiting 2 s then 4 s. The garage shows Closing; when the save returns, the folder is destroyed, the slot is freed and the garage resets to the empty stage 1 look (section 3.3). Shutdown still goes through `BindToClose` (:915-919). A player who leaves during their claim's load is covered by the existing "they left while loading" checks (:775, :788, :790, :833); nothing is saved because `data.loaded` is still false (:485).

**A late joiner** sees the plaza and six garages. Taken ones show the owner's stage building and name, and their room when walked into, as open plots do today. Free ones show a green FREE sign and a lamp (Neon, no PointLight). Closing ones say "Closing...". A new client script, `LobbyClient`, shows a banner ("Walk to a free garage to start your company") and an arrow to the nearest Free garage, drawn from the garage attributes.

**An unclaimed player** can walk, chat, look into other garages through their open doors and read the in-server leaderboard. Shop, eggs, team, poach, IPO, daily claim and calls are refused by the server with today's "Still loading" messages. Two rough edges:

- **Robux:** a product bought before claiming waits up to 30 s for data (ShopServer.lua:32, 515-525), then returns `NotProcessedYet`; Roblox retries later and the receipt list prevents a double grant. Nothing is lost, but it confuses, so Robux buttons are greyed out until the player has a garage (attribute `Garage`, 0 = none).
- **VIP Lounge:** passes are read at claim now (`ShopServer.setupPlayer`), so an unclaimed VIP at the lounge door is offered the pass again (ShopServer.lua:683-694). Accepted for v1.

**Respawn.** After a claim, a reset respawns the player at their own garage door (today's `CharacterAdded` hook, :865-870, moved into `claimGarage`); before a claim, at the plaza. Open question 1.

**Server authority.** The client only presses a prompt. It never names a player, a price, a position or a state; the server decides and writes every attribute.

## 2. TycoonCore: what changes and what must not

### 2.1 What changes

| Today | New | Lines |
|---|---|---|
| Join picks the first free slot or kicks the 7th player | `claimGarage` takes the slot the player chose. No "server full" kick: with no Free garage the player waits (only possible during a Closing) | :735-746 |
| `leaderstats` made on join | made in `claimGarage`, right before `load` | :748-758 |
| Folder and `Floor` per player | six permanent garages built at server start, each with its own `Floor` (the only solid part), restyled per owner's stage; the player's folder goes inside the claimed garage | :760-768 |
| `plotCenter(slot)`: a row 90 apart, all facing +Z | `plotFrame(slot)`: position and quarter turn from `LobbyConfig.Garages`; `plotCenter` stays as `plotFrame(slot).Position` | :76, :78, :125-128 |
| `teleportToPlot` on join and every respawn | none on join; respawns after a claim land at the garage door facing in, after `player:RequestStreamAroundAsync` in `pcall` (missing today: WORLD_PASS_PROPOSAL.md:41) | :725-732, :865-870 |
| `data.ready = true` at the end of the join | same spot at the end of `claimGarage`, still after `refreshSign` | :862-863 |
| `PlayerRemoving` frees the slot | same, plus reset the garage to Free | :880-888 |

**Kill switch.** With `LobbyConfig.ClaimEnabled = false`, join picks the first Free garage, calls `claimGarage` itself and teleports the player in: today's behaviour through the same function. It stays off until PR L3's Studio tests pass, and turning it off is the live fallback.

**The Cash bar's loading rule.** IpoClient keeps Cash and Income empty until the attribute `Upgrade1` appears (IpoClient.lua:38-43). `publishUpgrades` sets it inside `refreshSign` (TycoonCore.lua:206-213), after the saved Cash, the income and the offline earnings and before `data.ready`. A 30 s fallback (`MONEY_WAIT`, IpoClient.lua:45) shows the values anyway, starting as soon as the bar finds `leaderstats` (IpoClient.lua:1000-1017). If `leaderstats` still appeared on join, a returning player in the plaza for 30 s would see **$0 and $0/s**, which looks like a wiped save. Making `leaderstats` at claim avoids it, and **IpoClient does not change**: with no `leaderstats` the bar stays empty (IpoClient.lua:958). tools/hud_test.py pins this by function name (`REFRESH_SIGN_SITES`, :1365; order checks, :1543-1572); they move to `claimGarage` with the same order (load, Cash, income, offline, `refreshSign`, `data.ready`).

### 2.2 What must not change

- **Saving:** `save()` (:483-516), `buildPayload` (:417-452), `saveOnLeave` (:528-544), the one-save lock, the `data.loaded` check (:485), the save gate (:486), autosave (:905-913), `BindToClose`. The `BUILDSAVE`, `SAVEFN`, `LEAVESAVE`, `REREAD` and `COMMITIPO` blocks stay byte-identical, and a new test compares them with `main`.
- **The save format:** `StartupTycoon_v1`, `player_<UserId>`, `KNOWN_SECTIONS` (:86). No new section or field. The garage is not saved. A "remember my garage" feature would need a new top-level section (rule A10, CLAUDE.md:142); I recommend never adding it.
- **Income:** the loop (:890-903), `updateIncome`, `addEarnings` as the one earnings path, the IPO commit.
- **Offline earnings:** the block at :850-860, unchanged. Side effect: minutes spent in the plaza before claiming count as "away" (50% rate, same cap), since `lastSeen` is compared with the claim time. That equals staying offline, so it is no exploit; fixing it would mean editing that block.
- **Module order** in the setup `pcall` (:796-832), `DailyServer` last. The block moves; it is not reordered.

### 2.3 Risk to saves

| # | Risk | Prevention |
|---|---|---|
| S1 | Moving 125 lines into `claimGarage` loses a "left while loading" check or sets `data.loaded` early, and a half-loaded session saves over a good save | block moved without edits; marker blocks compared with `main`; hud_test order checks; mutants for each |
| S2 | One player gets two data tables (two claims, or a claim plus the kill-switch auto-claim), so two sessions write one key and the last wins | one claim per player, checked with no yield; two-claims-in-one-tick test; mutant |
| S3 | A player leaves during the load and the garage is freed while the load still writes | today's `playerData[player] ~= data` checks kept; "leave during load saves nothing" test |
| S4 | A player who never claims | never reads, never writes: their save is untouched |
| S5 | The two-server gap (F10) gets worse | no: the read happens later, and the 7 s re-read still applies |
| S6 | A Robux receipt before claiming | delayed, never lost or doubled; buttons greyed out |
| S7 | Rollback to an older version | nothing new is saved; the rollback floor (docs/PUBLISH_RULES.md) is unchanged |

## 3. The building

### 3.1 What `building-pass` gives, and how it fits

`origin/building-pass` (not merged; 9 commits of new files, 306 behind `main`) has `PlotBuilding.lua` (data), `PlotBuildingVisuals.lua` (builder, checks), `docs/studio_scripts/BuildingClient.lua` (the roof fade), `tools/building_test.py` (398 checks, 57 mutation runs) and an integration patch. Around each stage's 60 x 60 room it builds a closed shell: walls 15 high, a flat roof, a front wall with a 9 x 9 doorway, windows, a sign, within its own 64-part budget (47 to 56 used). The whole shell fades for the local player inside, client only, nothing saved (BUILDING_PASS_PROPOSAL.md sections 2, 4, 5).

**It fits, with four changes:**

1. **Doors face three directions.** Its inside check assumes the door on +Z. The client must first convert the character's position into the garage's frame (`CFrame:PointToObjectSpace`); the server puts the frame on the model as an attribute.
2. **Its patch is stale:** it targets the old TycoonCore (`77ce9c43...`, STUDIO_SYNC_BUILDING.md (a)). `PlotArt.lua` and `PlotVisuals.lua` are unchanged since its base `7f5c141` (`git diff` shows nothing), so its room fingerprints should hold; I did not run its tests. The three-edit hook is redone on `main`.
3. **Streaming:** its notes assume StreamingEnabled off; the world pass says it is on (WORLD_PASS_PROPOSAL.md:34). Both **unverified**; section 3.6 covers it.
4. **Customize said "park it"** (CUSTOMIZE_PROPOSAL.md:191): its shell is 60 x 60 and its roof blocks the edit camera. The lobby needs it now. The shell must take its size from the building (60 x 60 now, up to 78 x 82 after customize PR 2), and customize PR 3 hides the roof in edit mode as planned (CUSTOMIZE_PROPOSAL.md:154).

`BuildingClient.lua` should sit at the repo root like every other script (CLAUDE.md, "one Studio script = one `.lua` file at the repo root").

### 3.2 What the "open shell" rules become

CLAUDE.md:33 and docs/PLOT_VISUALS.md:31 say shells stay open (side walls 6 at most, back 12, no roof, no front wall); PLOT_VISUALS.md:50-52 calls the closed building "not built yet". Proposed wording, applied in PR L2:

> **The room stays open; the building around it is closed.** `PlotArt` rooms keep their low walls and no roof (checks and fingerprints unchanged). Around each room, `PlotBuilding` builds four walls, a front wall with a 9 x 9 doorway and a roof, as its own Model with its own budget (64 parts, 0 lights), faded for the local player inside by `BuildingClient`. Every building part is anchored with `CanCollide`, `CanTouch` and `CanQuery` off unless the owner decides otherwise (open question 2). "Front" means the garage's own front, toward the plaza.

The other rules stay: fixed gameplay positions (now in the garage frame), 260 parts and 3 lights per room, the materials, no odds text, nothing saved.

### 3.3 Inside the empty building at stage 1

A **Free** garage shows the permanent `Floor` in stage 1 style; the stage 1 shell (rusty sheets, tarp roof, roll-up door pulled up), about 51 parts; and the stage 1 room **without** the six props: crates, bare bulb, old PC, desk phone, taped window. That is 256 minus the props' 118 (PLOT_VISUALS.md:34) = **138 parts**: an abandoned garage, ready for someone. No employees, incubators or signs (they belong to an owner's folder), and the FREE sign over the door.

A **new** player who claims it gets exactly this plus today's first minute (free egg, arrow, goals). A **returning** player gets their stage's building and room with props, employees and incubators, rebuilt from the save. Every position is relative to the garage: `itemOffset` (TycoonCore.lua:133-137), hire spots and incubators (EmployeeServer.lua:31-41), the IPO sign (IpoServer.lua:21), customize items' `x`, `z` from the anchor (CUSTOMIZE_PROPOSAL.md:51, 98). That is why any garage works.

**Customize placement area.** CUSTOMIZE anchors the building at the floor's front-center and lets it grow back and sideways to 78 x 82, plus 2.3 of shell per side (CUSTOMIZE_PROPOSAL.md:98-99); items go inside it minus the reserved zones (`CompanyConfig.checkPlacement`). Each ring lot reserves that largest size from day one (section 4.2), so customize never moves a garage.

### 3.4 Doorway, camera and roof fade

The doorway is 9 x 9, centered on the garage's walking lane (x -4.5 to 4.5 in its frame). The claim post stands 3 studs outside, beside the lane. The 3.5-stud apron in front counts as inside, so the front wall starts fading as the player walks up. Doors are open to everyone: visiting a garage is allowed, as walking onto a plot is today.

The default camera sits behind the player. Walls are non-solid today because "a solid wall makes the camera zoom in" (PLOT_VISUALS.md:32). Inside, the whole shell fades in 0.4 s and the player sees today's open room; outside it looks solid. But anyone can walk through a wall, so a "real" building may want solid outer walls (open question 2). How the camera treats solid walls that fade is **unverified**.

### 3.5 Phone performance

| What | Parts |
|---|---|
| Taken garage, biggest stage (room 257 + building 56) | about 313 |
| Free garage (empty room 138 + building 51 + sign and post) | about 195 |
| Six taken garages | about 1,880 |
| Plaza and paths | world pass budget 600; 268 built for the row |

All anchored, shadows off on small parts, at most 3 PointLights per room, none on buildings, 6 in the world. Customize's planned 320 per room (CUSTOMIZE_PROPOSAL.md:106) adds about 380 for six garages.

**StreamingEnabled.** The default minimum radius is 64 studs **(unverified for this place)**. Doors are 93 studs from the spawn and the far corners about 200, so on a low-memory phone a garage may not have arrived and the player can't see if it is free. So each garage's **shell, sign and claim post** are a Model with `ModelStreamingMode = Persistent` (always sent; about 60 parts each); **rooms, props and employees** stream as today; respawn teleports call `RequestStreamAroundAsync`. `BuildingClient` costs 6 small inside checks per frame. Frame rate on a low-end phone is **unverified**.

## 4. The plaza and the ring of garages

### 4.1 Does the existing world pass fit?

Partly. `WorldArt.lua` and `WorldVisuals.lua` are on `main` but **not wired** (STUDIO_SYNC_MASTER.md:9-12), and their TycoonCore patch needs regenerating. Their layout is a **row**: spawn plaza at the origin, an avenue to the lounge, streets along six plots at z 150 (WORLD_PASS_PROPOSAL.md section 4). Reused as is: the pieces (lamps, trees, benches, planters, arch, number signs), the palette, the materials, the rules and their named checks (WORLD_PASS_PROPOSAL.md section 5), the builder, the preview and cleanup blocks. New: a `ring` layout fed by `LobbyConfig.Garages` instead of `PLOT_SPACING` and `MAX_PLOTS`. The row patch (`docs/world_pass_integration.patch`) is **never applied**.

### 4.2 Layout with 6 garages

The VIP Lounge stays where it is (ShopServer.lua:35-38: center (0, 70), walls x ±18.5, z 57.5 to 82.5), its door facing +Z. The plaza sits **in front of that door**, so the lounge closes the ring's fourth side:

```
              +Z
        [ G3 ]  [ G4 ]          north: doors face -Z
  [G2]                  [G5]
          PLAZA 180 x 180       center (0, 175), spawn here
  [G1]                  [G6]    west doors face +X, east doors face -X
            [ LOUNGE ]          door faces +Z, onto the plaza
```

| | Number |
|---|---|
| Plaza | 180 x 180, center **(0, 175)**: x -90 to 90, z 85 to 265 |
| SpawnLocation | moved **by hand** to (0, 0.5, 175); today a Studio fact at (-1, 0.5, -1) (WORLD_ICONS_NOTES.md:94) |
| Front line (anchor, floor front-center) | 93 studs from the plaza center |
| G1, G2 (west, face +X) | anchors (-93, 130), (-93, 220); floor centers (-123, 130), (-123, 220) |
| G3, G4 (north, face -Z) | anchors (-45, 268), (45, 268); floor centers (-45, 298), (45, 298) |
| G5, G6 (east, face -X) | anchors (93, 220), (93, 130); floor centers (123, 220), (123, 130) |
| Lot | 82.6 wide x 86.6 deep: customize's 78 x 82 plus 2.3 of shell per side |
| Gaps | 7.4 between a side's two garages (CUSTOMIZE_PROPOSAL.md:99's rule); 6.7 at each corner; 6.2 from the lounge |
| Spawn to a door | 93 studs, about 6 s of walking; farthest part about 200 |

Everything is inside the Baseplate and clear of `PREVIEW_STAGES`. The lounge door approach and the non-VIP drop spot (0, 88) (ShopServer.lua:832-844) stay clear, as the world rules already require. Decor: paving, a path from each door to the center, lamps (lit only around the spawn), benches, planters, trees in the gaps, a number sign per garage, the arch over the spawn.

**Why turned garages, and the cost.** Garages around a plaza must face it, so four of six turn (90°, 180°, 270°). Only quarter turns: boxes stay axis-aligned, so the existing box checks work after swapping x and z. The change is wherever code does "center + offset": TycoonCore (`spawnItem`, `refreshSign`, `teleportToPlot`), EmployeeServer (`placeEmployees` and its facing, incubators), IpoServer (`buildSign`), PlotVisuals (`floorOrigin`, PlotVisuals.lua:183-185, since every part is placed from that base, plus `check`), EmployeeClient (the wander code starts every employee facing world +Z), and PlotBuilding/BuildingClient. PR L1 does it with every turn at 0°, so nothing moves.

### 4.3 Max Players

- **The docs say 6:** PUBLISH_RULES.md:5-11 ("must be 6"; change it with the plot count), ROADMAP.md:55, STUDIO_SYNC_MASTER.md:124, :380.
- **Studio showed 60** (owner's report; I did not open Studio), so the setting was never applied. If the game were public today, a 7th joiner would be kicked at once (TycoonCore.lua:742-743). After this change they would stand in a plaza with nothing to do, which is worse.

**Recommendation: 6**, set in Game Settings > Places (or Creator Hub) in the same release as PR L3 and checked after every publish. **Cost:** no code, one setting, more and smaller servers. With 6 players and 6 garages a joiner always finds a Free garage, or a Closing one that frees within seconds, so FR-3 stops being a kick.

**Alternatives.** Eight garages with Max 8 means two lots beside the lounge, one layout PR, about 630 more parts, and a new phone and server test; consider it only with real player numbers. More players than garages (10 on 6) leaves people with nothing to do: not recommended.

## 5. Build plan

Each PR starts from the latest `main`, claims its files in CONTRIBUTING.md and lists its Studio steps in `docs/STUDIO_SYNC_LOBBY.md`. A "mutant" is a deliberately broken copy the tests must catch by a named check.

**Order against other branches.** `world-icons-pass` is in `main`, unwired; L4 wires it in ring form. `building-pass` is unmerged and far behind; L2 takes **its new files only**. Customize PR 2 (the building engine) waits for L2 and L4 (frame and lot size). `design-tutorial` gains a step 0, "claim a garage".

**L1. Plot frame (nothing visible changes).** `TycoonCore` (`plotFrame`, three call sites), `EmployeeServer`, `IpoServer`, `PlotVisuals`, `EmployeeClient`; every turn 0°.
- *Tests:* daily_test.py: with no turn, `plotFrame` equals today's `plotCenter` for all six slots; room, props, hire spots, incubators and both signs built at 90°, 180° and 270° equal the 0° build turned; fingerprints unchanged. world_test.py reads `plotCenter` and the landing line as text (:900-913), so its patterns follow.
- *Mutants:* IPO sign offset not turned; employee facing ignores the turn; turn sign flipped; `PlotVisuals.check` in world axes.
- *Studio:* paste five scripts, hash block, playtest: nothing moved.

**L2. The closed building (still the row, still auto-assign).** `PlotBuilding`, `PlotBuildingVisuals`, `BuildingClient` (created by hand) and `tools/building_test.py` from `building-pass`; the hook redone on `main`; the inside check in the garage frame; the new CLAUDE.md and PLOT_VISUALS.md rule.
- *Tests:* building_test.py's 398 checks and 57 mutation runs re-run on `main` (its "no existing file edited" check moved to the new base); inside check and door apron at four turns; daily_test.py's wiring list gains the three scripts.
- *Mutants:* client check in world axes (caught at 90°); apron on the wrong side; a building part made solid.
- *Studio:* create three scripts, paste TycoonCore, preview, walk in and out, Test > Device. Can ship alone.

**L3. The claim (behind `ClaimEnabled`).** New `LobbyConfig` (ReplicatedStorage: garage list, distance, texts, `ClaimEnabled`, a pure `canClaim(state, player, slot, rootPosition, now)` tested like `CompanyConfig.checkPlacement`). TycoonCore: `onPlayerAdded` split, `claimGarage` between new `CLAIM-START`/`CLAIM-END` markers, permanent garages and states, prompts, reset on leave. New `LobbyClient` (by hand): banner, arrow, Robux buttons greyed.
- *Tests:* new `tools/lobby_test.py` with fake players, DataStore and scheduler: the four states; one claim per player; two claims in one tick; distance (far, NaN, infinite, no character); bad slots; leave during load frees and saves nothing; failed load kicks and frees; rejoin while the old leave save runs; `ClaimEnabled` off = auto-assign and teleport. hud_test.py's coupling checks point at `claimGarage`, plus "`leaderstats` made there, not on join". daily_test.py keeps :7028 and rewords :7040 ("spawning buys nothing"). Save blocks compared with `main`.
- *Mutants (about 15):* no one-claim check; a yield between check and write; garage freed before the leave save ends; `data.ready` before `refreshSign`; `leaderstats` on join; no distance check; prompt on for a Taken garage; no reset on leave; kill-switch path without teleport.
- *Studio:* create two scripts; Test > Clients and Servers with 2 and 3 players: both claim one garage, leave and rejoin, late join, a returning save in a different garage, the banner at phone size. Then turn `ClaimEnabled` on.

**L4. Ring and plaza.** `LobbyConfig.Garages` gets the ring; `WorldVisuals` gets the ring layout and its TycoonCore hook in `pcall`; garage shells `Persistent`; the row patch marked superseded.
- *Tests:* world_test.py builds the ring from `LobbyConfig` with every named check, keep-outs for each full-size lot, the lounge, drop spot and moved spawn pad, and a sweep of building sizes from 62 x 62 to 82.6 x 86.6; render_previews.py draws a new top-down SVG.
- *Mutants:* two lots overlapping; a path through a doorway; a lot off the Baseplate; spawn pad covered; a garage facing away.
- *Studio:* **move the SpawnLocation by hand** to (0, 0.5, 175) (the preview prints whether it matches), check the default camera, walk to each garage on a phone, watch streaming.

**L5. Docs and publish.** CLAUDE.md, ROADMAP.md status, README rows, PUBLISH_RULES section 1 ("6 = the garage count"). Set Max Players 6, run the pre-publish list, publish with **Shut down all servers** (the save format is unchanged, but old servers run the old flow).

## 6. Open questions for the owner

1. **Respawn after a reset: plaza or own garage door?** *Recommended: own door* (today's hook, less walking).
2. **Solid outer walls?** *Recommended: not solid in v1*, then a one-flag Studio test of solid walls.
3. **Max Players?** *Recommended: 6*, set with the claim release; revisit 8 with real player data.
4. **Can a player move to another garage mid-session?** *Recommended: no in v1* (it means rebuilding a loaded company).
5. **Keep the lounge and build the plaza in front of its door, moving the SpawnLocation by hand?** *Recommended: yes* (no ShopServer change).
6. **What a free garage shows inside?** *Recommended: the stage 1 room without props* (138 parts); the alternative is a bare floor.
7. **Ship the claim behind `ClaimEnabled`, off until the 2-player Studio test passes?** *Recommended: yes.*

## 7. What I did not verify

- **Nothing was run:** no test, no Luau, no Studio. I read code and docs; line numbers are from `main` `99eed7b`.
- **Max Players 60** is the owner's report; the 6 comes from the docs.
- **StreamingEnabled** being on, and its radii (the world pass marks them unverified; building-pass assumed off).
- Server-side ProximityPrompt distance checks; the camera with solid fading walls; setting `ModelStreamingMode = Persistent` from a script; DataStore read times; the sign of a turn in Roblox (tests will pin it).
- That building-pass's tests pass on `main`; I only checked that `PlotArt.lua` and `PlotVisuals.lua` are unchanged since its base.
- Part counts for the empty room and the ring plaza are estimates from the docs' numbers, not builds.
- How the HUD (valuation bar, chips, task tray) looks for an unclaimed player. Every server path refuses cleanly; the clients' empty states were not checked.
