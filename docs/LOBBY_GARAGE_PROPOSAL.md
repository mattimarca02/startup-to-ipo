# Lobby and garages proposal: one plaza, six garages you walk to and claim

Design only (2026-10-15, branch `lobby-garage`, from `main` `99eed7b`; revised the same day after an independent review). No code, no `.lua` edit, nothing in Studio. Line numbers are `main` `99eed7b` unless a branch is named. **(unverified)** marks what I could not check from the repo.

**Owner decisions (final):** (1) one common server and one shared plaza; a player spawns there, never at a garage, with no teleport to another place; (2) a player walks to a free garage and claims it; a returning player gets their saved company in whichever garage they claim (the company lives in the save, not the slot), a new player starts from zero; (3) a closed building with a complete interior, from `building-pass`; (4) **outer walls solid from the first version** (section 3.4); (5) **6 garages, Max Players 6**; (6) **no moving between garages** in a session; (7) **keep the VIP Lounge**, the plaza in front of its door, plus a code fallback that puts a player on the plaza on their first spawn; (8) **a Free garage shows today's new-player room, unchanged** (section 3.3); (9) **the claim ships behind an off switch**, `LobbyConfig.ClaimEnabled`.

A **garage** is one of the six lots (the code says plot or slot); **claim** means "this garage is mine for this session".

## 0. The short version

On join the player only enters the plaza. Each Free garage has a **"Claim garage" prompt**. The server checks the request, then runs **today's loading code, byte-identical, with that slot**; the code around it (folder, `Floor`, label, respawn hook) is rewritten, because the garage becomes permanent. The save format does not change: the slot was never saved (TycoonCore.lua:423-436). Six garages face a 180 x 180 plaza in a horseshoe open on the lounge side, so the code learns quarter turns. Six pull requests, the first two with no visible change.

## 1. From join to a claimed garage

### 1.1 Today

`onPlayerAdded` (TycoonCore.lua:734) takes the first free slot (:735-741), kicks a 7th player (:742-744), marks the slot (:746), makes `leaderstats` (:748-758), the folder, the `Floor` and its "X's Startup" billboard (:760-768). It reads the save (:774; a failed read kicks, :776-782; a fresh save is read again after 7 s, :786-794), sets up the modules in one `pcall` (:796-832), turns saving on (`data.loaded`, :839), builds the room (:842), pays offline earnings (:850-860), calls `refreshSign` (:862), sets `data.ready` (:863) and hooks `teleportToPlot` (:725-732) to every spawn (:865-870). On leave, `saveOnLeave` runs before the folder is destroyed and the slot freed (:880-888), so the slot stays taken while the save runs (FR-3, docs/reviews/FULL_REVIEW.md:171).

### 1.2 The new flow

**Join.** `onPlayerAdded` writes a plaza marker (`inPlaza[player] = true`) **before its first yield** and stops: no slot, no `leaderstats`, no folder, no save read. The guard for players who joined before the script started (:874-878) checks that marker instead of `playerData`, so nobody is set up twice. On the first spawn, a character more than 100 studs from the plaza center is moved to `LobbyConfig.PlazaSpawn` (decision 7's fallback). With `playerData[player]` empty, every server path already refuses: EmployeeServer.lua:485-486, IpoServer.lua:267-268, PoachServer.lua:70, TaskServer.lua:504-507, CompanyServer.lua:74-76, DailyServer.lua:219, TycoonCore.lua:274-278.

**States.** `plotOwners[slot]` (TycoonCore.lua:88) stays the only truth: **Free**, **Moving in** (save loading), **Taken**, **Closing** (leave save running). Attributes `State` and `OwnerName` on the garage are for display; nothing reads them back.

**The claim.** A Free garage has a ProximityPrompt "Claim garage" on a post beside its door (hold 0.5 s, 10 studs), as the incubators do (EmployeeServer.lua:531-543); no touch handler, so tools/daily_test.py:7028 stays true. The server checks, in one block **with no yield between the check and the write** (CLAUDE.md's daily-claim rule):

1. **one claim per account:** `claims[player.UserId]` is empty (section 1.3);
2. the slot is a whole number from 1 to 6 and is Free;
3. the root part is within 14 studs of the door, measured on the server (Roblox may check prompt distance itself **(unverified)**);
4. at most one request per second per player;
5. `ClaimEnabled` is on.

If all pass: `claims[userId] = slot`, `plotOwners[slot] = player`, Moving in, prompt off, load starts. Otherwise a short message ("Taken by Ana, try another", "Your last visit is still saving, try again in a few seconds"). Two prompt events run one after the other; with no yield between check and write, the first wins.

**Moving in.** `claimGarage(player, slot)` makes `leaderstats`, sets the locals the moved block uses, then runs it (section 2.1). The sign says "Moving in...". A read takes about a second **(unverified)**; a save under 75 s old waits 7 s more (:387-388); a read that keeps failing ends in today's kick, which frees the garage.

**The owner leaves.** `saveOnLeave` (:528-541) as today: up to 3 tries, waiting 2 s then 4 s. The garage shows Closing; when the save returns, the folder is destroyed, the garage reset (section 2.2), the slot freed, and only then `claims[userId]` cleared. `BindToClose` (:915-919) is unchanged. A player who leaves during the load is covered by the four "left while loading" checks (:775, :788, :790, :833); nothing is saved because `data.loaded` is still false (:485).

**A late joiner** sees Taken garages with the owner's building and name, Free ones with the new-player room, a green FREE sign and a lamp (Neon, no PointLight), Closing ones saying "Closing...". A new `LobbyClient` shows a banner ("Walk to a free garage to start your company") and an arrow to the nearest Free garage.

**Respawn.** After a claim, at the player's own garage door; before, on the plaza. Open question 1.

**Server authority.** The client only presses a prompt; it never names a player, price, position or state.

### 1.3 Rejoining while the old garage is Closing

The same account can rejoin (a reconnect, a second device) while its old leave save is still running. Keyed on the `Player` object, the new session could claim a second garage and read the save before that leave save lands: the 7 s re-read (:388) covers only a leave save that finishes within 7 s, and `saveOnLeave` alone can wait 6 s plus three DataStore calls. So the claim is keyed on **`UserId`** and **held until that leave save has returned** (:880-881); until then the prompt says "still saving", and with `ClaimEnabled` off the auto-claim waits. lobby_test case: rejoin during Closing with the leave save delayed past 7 s; the claim is refused until it returns, then the read sees it. Mutant: claim keyed on `Player`.

### 1.4 An unclaimed player

They walk, chat and look into garages. Shop, eggs, team, poach, IPO, daily claim and calls refuse them with today's "Still loading" messages.

- **Robux products.** A receipt for a player with no data waits 30 s (ShopServer.lua:32, `waitForData` :516-525), then returns `NotProcessedYet` (:570-573). The comment says Roblox retries on rejoin; when Roblox retries is **(unverified)**. The receipt list prevents a double grant. **Fix (L3):** no deadline while the player is in the server with no claim; 30 s from the claim, read through a new `core.claimedAt(player)`. Whether Roblox limits a callback that waits that long is **(unverified)**. Robux buttons are greyed out until the player has a garage (attribute `Garage`, 0 = none).
- **The lounge door prompts from the server** (ShopServer.lua:683-694): `hasEffect` finds no data (:79-81), so an unclaimed VIP is offered their own pass, and greyed buttons don't stop it. **Decision:** for a player with no data the door says "Claim a garage first: your passes load with your company" and prompts nothing.
- **The lounge loop** (ShopServer.lua:833-844) puts anyone without the `vipLounge` effect back at (0, 88). **Decision:** keep it; (0, 88) is the plaza's lounge edge, and passes count from the claim.
- **Clients waiting for `leaderstats`:** IpoClient.lua:695 and ShopClient.lua:1589 call `WaitForChild("leaderstats")` with no timeout, which warns "infinite yield" after 5 s for every plaza player. L3 makes both a quiet `ChildAdded` wait and rewrites IpoClient's comment at :38-42 (it says `leaderstats` exist from the join).

## 2. TycoonCore: what changes and what must not

### 2.1 The code that moves, proven unchanged

Only **:774-863** moves: the read, the four checks, the re-read, the setup `pcall`, `data.loaded = ok` (:839), the room (:842), props, `updateIncome`, offline earnings, `refreshSign`, `data.ready`. The folder, `Floor` and label (:760-768) and the respawn hook (:865-870) are rewritten (section 2.2).

1. **L0**, a no-op PR, adds `-- CLAIMLOAD-START` / `-- CLAIMLOAD-END` around :774-863 on `main`.
2. **No later PR edits between the markers.** L1 keeps :842's `plotCenter(slot)`: `PlotVisuals` takes the turn from the `floor` it already receives (`floor.CFrame`).
3. L3 moves the marked text into `claimGarage`, after locals with the names it uses (`player`, `slot`, `data`, `folder`, `floor`, `cash`, `income`).
4. `tools/lobby_test.py` compares it **byte for byte with `main`'s** (`git show origin/main:TycoonCore.lua`) and runs it with fakes (DataStore, the modules, a player leaving at each yield).
5. **Mutants:** each check (:775, :788, :790, :833) removed in turn; `data.loaded = ok` moved above :833; `data.loaded = true` instead of `ok`; `leaderstats` made after `load`.

### 2.2 The permanent garage (L2)

Today the `Floor` (:767), the room (:842) and building-pass's hook live in the per-player folder, destroyed on leave (:884). **L2** (still the row, still auto-assign) makes the garage permanent:

- **`buildGarages()`** at server start makes `Workspace.Garages.Garage1..6`, each with the `Floor` (60 x 60, the room's only solid part, turned by the frame) and the stage 1 building.
- **The billboard goes.** "X's Startup" (:768) is no longer added to the `Floor`, which would stack one per claim; the owner's name goes on the garage sign, set on claim, cleared on reset.
- **The owner's folder** (room, props, employees, incubators, signs) sits inside the garage and is still destroyed on leave; :842 is unchanged.
- **building-pass's hook goes outside the moved block:** `syncBuilding(garage, stage)` is called by `buildGarages` (stage 1), by `syncRoom` on a stage change (as its patch does) and by the reset. Its third edit, after :842, is dropped (the building already stands). L3 does not redo it.
- **Reset on leave**, after the leave save: destroy the folder, restyle `Floor` and building to stage 1, clear the sign. L3 adds the Free room, FREE sign and prompt.

### 2.3 What else changes

| Today | New | Lines |
|---|---|---|
| First free slot or kick | plaza on join; `claimGarage` takes the chosen slot; the kick stays only as the cap | :735-746 |
| `leaderstats` on join | in `claimGarage`, right before the moved block | :748-758 |
| `plotCenter`: a row 90 apart facing +Z | `plotFrame(slot)` from `LobbyConfig.Garages`; `plotCenter` = `plotFrame(slot).Position`; `MAX_PLOTS` stays 6 | :76-78, :125-128 |
| `teleportToPlot` on join and respawn | respawns after a claim land at the door, after `RequestStreamAroundAsync` in `pcall` (WORLD_PASS_PROPOSAL.md:41) | :725-732, :865-870 |
| `PlayerRemoving` frees after the save | same order, plus Closing, reset, then `claims[userId]` cleared | :880-888 |

**The cap (L3).** Nothing in the code reads `Players.MaxPlayers`. At startup the server warns if it is above `#LobbyConfig.Garages` (FULL_REVIEW.md:564's safety net). A joiner is kicked with today's text (:743) **only when there are more players than garages**.

**Kill switch.** With `ClaimEnabled = false`, join calls `claimGarage` itself on the first Free garage and teleports the player in: today's behaviour through the same function. **With no Free garage** (one Closing, or Max Players above 6), the player waits on the plaza and the server retries every second; a Closing garage frees when its leave save returns. After 60 s, today's kick (:742-744). `LobbyConfig` is a ModuleScript, so **the switch is not live**: flipping it is a Studio edit plus a publish, and running servers keep the old value until they restart (**Shut down all servers** applies it everywhere). It stays off until L3's Studio tests pass.

**The Cash bar's loading rule.** IpoClient shows Cash and Income only once `Upgrade1` appears (IpoClient.lua:38-43; set by `publishUpgrades`, TycoonCore.lua:206-212, inside `refreshSign`, before `data.ready`), or 30 s after it finds `leaderstats` (`MONEY_WAIT`, :45, :1000-1017). With `leaderstats` made on join, a returning player 30 s in the plaza would see **$0 and $0/s**, like a wiped save. Made at claim, the bar stays empty until then (:958).

### 2.4 What must not change

- **Saving:** `save()` (:483-519), `buildPayload` (:417-453), `saveOnLeave` (:528-541), the one-save lock, the `data.loaded` check (:485), the save gate (:486), autosave (:906-913), `BindToClose`. `BUILDSAVE`, `SAVEFN`, `LEAVESAVE`, `REREAD`, `COMMITIPO` and the new `CLAIMLOAD` stay byte-identical, compared with `main`.
- **Save format:** `StartupTycoon_v1`, `player_<UserId>`, `KNOWN_SECTIONS` (:86). The garage is not saved. "Remember my garage" would need a new section (rule A10, CLAUDE.md:142); I recommend never adding it.
- **Income:** the loop (:891-903), `updateIncome`, `addEarnings` as the one earnings path, the IPO commit.
- **Offline earnings** (:850-860). Plaza minutes before the claim count as "away" (50%), like staying offline: no exploit.
- **Module order** in the setup `pcall`, `DailyServer` last.

### 2.5 Risk to saves

| # | Risk | Prevention |
|---|---|---|
| S1 | The move loses a "left while loading" check or sets `data.loaded` early; a half-loaded session saves over a good save | markers on `main` first; byte compare; the block run with fakes; section 2.1 mutants; hud_test order checks |
| S2 | One account gets two data tables (two claims, claim plus auto-claim, rejoin during Closing): two sessions write one key | one claim per `UserId`, held until the leave save returns, no yield; tests and mutants |
| S3 | A leave during the load while the load still writes | the four checks; "leave during load saves nothing" test |
| S4 | A player who never claims | never reads, never writes |
| S5 | The two-server gap (F10) widens | no: the read is later, the re-read stays, the `UserId` hold covers this server |
| S6 | A Robux receipt before claiming | waits for the claim; never lost or doubled |
| S7 | Rollback | nothing new is saved; rollback floor (docs/PUBLISH_RULES.md) unchanged |

## 3. The building

### 3.1 What `building-pass` gives, and how it fits

`origin/building-pass` (unmerged; 9 commits, 306 behind `main`) adds `PlotBuilding.lua`, `PlotBuildingVisuals.lua`, `docs/studio_scripts/BuildingClient.lua` (the fade), `tools/building_test.py` (398 checks, 57 mutation runs) and an integration patch. Around each 60 x 60 room: walls 15 high, a flat roof, a front wall with a 9 x 9 doorway, windows, a sign, 47 to 56 of 64 parts. The shell fades to fully transparent for the local player inside (BUILDING_PASS_PROPOSAL.md sections 2, 4, 5).

**Its state against `main`** (git only, no test run):

- Of existing files it changes only `CONTRIBUTING.md`. A merge with `main` conflicts only there: keep both sides' rows.
- Two of its checks fail on any branch containing today's `main`, only because `main` moved: "no existing file is edited" and "tools/daily_test.py is untouched" compare with its base `7f5c141` (building_test.py:1319-1342), and `main` has changed 14 files since, `daily_test.py` among them. **The first PR that merges it (L2)** makes both compare with that PR's merge base.
- `PlotArt.lua` and `PlotVisuals.lua` are unchanged since `7f5c141`, so its room fingerprints should hold.
- **Whether its patch applies to `main`'s TycoonCore is not verified.** L2's first step is `git apply --check docs/building_pass_integration.patch` on `main`; either way L2 takes only two of its three edits (section 2.2).

**Four changes:** (1) **doors face three directions**: the client converts the character's position into the garage frame (`CFrame:PointToObjectSpace`), from a frame attribute the server sets; (2) **solid outer walls** (section 3.4); (3) **streaming**: its notes assume StreamingEnabled off, the world pass says on (WORLD_PASS_PROPOSAL.md:34), both **unverified**; (4) **customize said "park it"** (CUSTOMIZE_PROPOSAL.md:191) because the shell is 60 x 60 and the roof blocks the edit camera: the shell takes its size from the building (up to 78 x 82 after customize PR 2), and customize PR 3 hides the roof in edit mode (CUSTOMIZE_PROPOSAL.md:154).

**Where `BuildingClient.lua` lives.** building_test.py reads it from `docs/studio_scripts` (:1144) and fails if it is at the root (:1293-1294). It becomes a game script, and CLAUDE.md says one Studio script = one root `.lua`, so **L2 moves it to the root and changes those lines**. It must then pass the root scans: daily_test.py:7028 (touch handlers) and :7123 (`addEarnings`), hud_test.py:1635, icon_test.py:1553, shop_ux_test.py:2691 (every `*Client.lua` ScreenGui) and :2811.

### 3.2 What the "open shell" rules become

CLAUDE.md:33 and PLOT_VISUALS.md:31-32 say shells stay open and nothing collides; PLOT_VISUALS.md:50-52 calls the closed building "not built yet". Wording for L2:

> **The room stays open; the building around it is closed.** `PlotArt` rooms keep their low walls and no roof (checks and fingerprints unchanged). Around each room, `PlotBuilding` builds four walls, a front wall with a 9 x 9 doorway and a roof, as its own Model (64 parts, 0 lights). Outer walls and roof are solid (`CanCollide` on, `CanTouch` off); every other building part has `CanCollide`, `CanTouch` and `CanQuery` off. `BuildingClient` fades the whole building for the local player inside. "Front" is the garage's own front, toward the plaza.

The rest stays: fixed gameplay positions (in the garage frame), 260 parts and 3 lights per room, the materials, no odds text, nothing saved.

### 3.3 Inside a Free garage

**Decision 8:** **today's new-player room, unchanged**: the stage 1 room from the same `PlotVisuals.newPlot` call, with no upgrade props because nobody owns any (props come only with owned upgrades, :843-847). The real reason this works: that room already lacks them. About **138 parts**: stage 1 with every prop is 256 (PLOT_VISUALS.md:18), minus the six upgrade props' 118 (PlotArt.lua:951; PLOT_VISUALS.md:34). The stage 1 decor stays whole (PlotArt.lua:216-325: crates, bare bulb, old PC, taped window and the `DeskPhone`, the call step's phone). No employees, incubators or signs; a FREE sign over the door.

On claim the Free room is destroyed and the moved block builds the owner's; the reset builds it again. A **new** player sees no change, then today's first minute (free egg, arrow, goals); a **returning** one gets their stage's room, props, employees and incubators. Any garage works because every position is relative to it: `itemOffset` (TycoonCore.lua:133-137), hire spots and incubators (EmployeeServer.lua:31-41), the IPO sign (IpoServer.lua:21), customize items (CUSTOMIZE_PROPOSAL.md:51, 98).

**Customize area.** The building grows from the floor's front-center to 78 x 82, plus 2.3 of shell per side (CUSTOMIZE_PROPOSAL.md:98-99). Each lot reserves that size from day one, so customize never moves a garage.

### 3.4 Solid walls: doorway, camera, fade, and the test that must pass

**Doorway lane.** The 9 x 9 doorway is centered on the walking lane (x -4.5 to 4.5 in the garage frame), which runs straight to the plaza path. Nothing solid stands in it. The claim post (3 studs outside the front wall, x +7), the lamp beside it and the FREE sign (over the door, above 9 studs) are non-solid and stay out of the lane and the reserved zones (PLOT_VISUALS.md:30). Doors are open to every visitor.

**Camera.** The default camera pulls in when an opaque solid part comes between it and the player; Roblox's camera script (`Popper`) ignores parts that are non-solid or at least 0.25 transparent **(from memory, unverified for the current PlayerModule)**. Solid parts cannot turn `CanQuery` off **(unverified)**, so walls must be transparent whenever they stand between the camera and a player inside:

- **Inside**, apron included (3.5 studs in front of the door), the whole shell fades to 1 in 0.4 s; it passes 0.25 about 0.1 s after the player reaches the apron, before the door.
- **Outside**, walls act like any building's: a camera swung behind a garage pulls in. Accepted.
- **The roof** fades with the walls; it is solid only so nothing stands in it.
- **Stage changes:** every solid part stays outside the floor and the lot's interior at every stage, so a swap never traps a player.

**Fade.** As building-pass: target 1 inside, 0 outside, 20 levels, client only, writes only `Transparency` (never `CanCollide`, which stays the server's).

**The test that must pass before L2 merges:**

- *building_test.py:* exactly the outer walls and roof are `CanCollide` on; every building part `CanTouch` off; the rest all three off; no solid part in the lane (9 wide, 9 high, apron to room), a reserved zone, aisle, hire spot or incubator; every solid part outside the floor at five stages and four turns; at full fade every solid part at least 0.25 transparent; the respawn landing and the claim post clear. *Mutants:* a door jamb in the lane; an inner part solid; the fade capped at 0.2; the roof left unfaded.
- *Studio:* at the default camera, walk in and out of each turn's door and stand inside facing each wall: the camera never pulls in. Walk every doorway, reset inside and outside, nobody stuck, Test > Device. If the camera pulls in anywhere, L2 waits for a fix.

### 3.5 Phone performance

| What | Parts |
|---|---|
| Taken garage, biggest stage (room 257 + building 56) | about 313 |
| Free garage (room 138 + building 51 + sign and post) | about 195 |
| Six taken garages | about 1,880 |
| Plaza and paths | world pass budget 600; 268 built for the row |

All anchored, shadows off on small parts, at most 3 PointLights per room, none on buildings, 6 in the world. Customize's planned 320 per room (CUSTOMIZE_PROPOSAL.md:106) adds about 380 for six.

**StreamingEnabled.** The default minimum radius is 64 studs **(unverified here)**; doors are about 105 studs from the spawn, far corners 200. So each garage's **shell, sign and claim post** are a `Persistent` Model (about 60 parts); **rooms, props and employees** stream as today; respawn teleports call `RequestStreamAroundAsync`. `BuildingClient` costs 6 small checks per frame. Low-end frame rate **unverified**.

## 4. The plaza and the ring of garages

### 4.1 Does the existing world pass fit?

Partly. `WorldArt.lua` and `WorldVisuals.lua` are on `main`, **not wired** (STUDIO_SYNC_MASTER.md:9-12), laid out as a **row** (WORLD_PASS_PROPOSAL.md section 4). Reused: the pieces, palette, materials, rules and named checks, builder, preview and cleanup. New: a `ring` layout fed by `LobbyConfig.Garages` instead of the row numbers at WorldArt.lua:33-45. The row patch (`docs/world_pass_integration.patch`) is **never applied**.

### 4.2 Layout with 6 garages

The VIP Lounge stays (ShopServer.lua:35-38: center (0, 70), walls x ±18.5, z 57.5 to 82.5), door facing +Z. The plaza sits **in front of that door**, so the lounge closes the ring's fourth side:

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
| SpawnLocation | moved **by hand** to (0, 0.5, 175); today (-1, 0.5, -1) (WORLD_ICONS_NOTES.md:94); the first-spawn fallback covers a missed move |
| Front line (anchor = floor front-center) | **95** from the plaza center |
| G1, G2 (west, face +X) | anchors (-95, 130), (-95, 220); floor centers (-125, 130), (-125, 220) |
| G3, G4 (north, face -Z) | anchors (-45, 270), (45, 270); floor centers (-45, 300), (45, 300) |
| G5, G6 (east, face -X) | anchors (95, 220), (95, 130); floor centers (125, 220), (125, 130) |
| Lot | 82.6 wide x 86.6 deep (78 x 82 plus 2.3 of shell per side): 2.3 in front of the anchor, 84.3 behind |
| Gaps | 7.4 between a side's two garages; **6.4 per axis (9.1 diagonal) at the corners**; both meet the 6-stud rule (CUSTOMIZE_PROPOSAL.md:99) |
| Spawn to a door | about **105** studs (95 is the front line), about 7 s of walking; farthest part about 200 |

The front line moved from 93: there G2 and G3 were 4.4 apart per axis (6.2 diagonal). Everything is inside the Baseplate, clear of `PREVIEW_STAGES` (x -630 to -290), with G1 and G6 74 studs from the lounge walls in x. The lounge door approach and the drop spot (0, 88) stay clear. Decor: paving, a path from each door to the center, lamps (lit only near the spawn), benches, planters, trees in the gaps, a number sign per garage, the arch over the spawn.

### 4.3 Turned garages: every "center + offset"

Four of six garages turn (west 90°, east 270°, north 180°). Only quarter turns, so boxes stay axis-aligned and box checks work after swapping x and z. Every site that adds an offset to the plot center:

- **TycoonCore:** `spawnItem`'s fallback (:197), `refreshSign` (:228), `teleportToPlot` (:729-730), the `Floor` (:767, moves to `buildGarages`), the room (:842, through `floor.CFrame`).
- **EmployeeServer:** center and home (:181, :185), facing `math.pi` (:192, :197), the `Home` attribute (:199, world position, fine once turned), incubators (:515-518).
- **IpoServer:** `SIGN_OFFSET` (:21) in `buildSign` (:293, :310).
- **PlotVisuals:** `floorOrigin` (:183-185), the base of every part, plus `check` and `zones`.
- **EmployeeClient:** the starting yaw `math.pi` (:966) faces world +Z and must take the turn; the wander (:988), walking yaw (:995) and pivot (:999) are in world axes and stay correct (pinned in L1).
- **CompanyServer:** placement is in anchor coordinates from `core.plotZones` (TycoonCore.lua:692-696) and must not change with the turn (L1 test).
- **WorldArt.lua:33-45**, **PlotBuilding**, **BuildingClient**.
- **Not affected:** PoachServer (its `core` comment names `plotCenter`; it never calls it) and OnboardingServer (it points at real parts' positions).

L1 does all of it with every turn at 0°.

### 4.4 Max Players

The docs say 6: PUBLISH_RULES.md:5-11; ROADMAP.md:55 ("Max Visitor Count = 6 in Creator Hub (place Access tab) and Social Slots = Roblox optimized"); STUDIO_SYNC_MASTER.md:124, :380. Studio showed 60 (owner's report; I did not open Studio). Nothing in the code reads it; today a 7th joiner is kicked (:742-743).

**Decision 5: 6.** Creator Hub checklist, at the L5 release and after **every** publish:

1. Creator Hub > the experience > **Places** > the **start place** > **Access** tab: **Max Visitor Count = 6**.
2. Same tab, **Social Slots** (server fill): Roblox optimized, as ROADMAP.md:55 says; if live servers log cap kicks, switch to the option that fills to the maximum.
3. **Other places in the universe:** list them; each reachable one gets the same value, or is confirmed unreachable.
4. **After the publish:** reopen the setting and check it reads 6; the startup warning (section 2.3) flags a wrong value in the server log.

Cost: one setting, more and smaller servers. A joiner always finds a Free garage or a Closing one about to free, so FR-3 stops being a kick.

## 5. Build plan

Each PR starts from the latest `main`, claims its files in CONTRIBUTING.md and lists its Studio steps in `docs/STUDIO_SYNC_LOBBY.md`. A "mutant" is a deliberately broken copy the tests must catch. Every TycoonCore PR keeps the word **"Touched" out of the whole file, comments included** (daily_test.py:7040 searches the raw text) and the saving blocks byte-identical.

**Order.** `world-icons-pass` is in `main`, unwired; L4 wires it in ring form. L2 takes `building-pass`'s new files and two of its three hook edits. Customize PR 2 waits for L2 and L4. `design-tutorial` gains a step 0, "claim a garage".

**L0. Markers (no change).** `CLAIMLOAD` markers around :774-863. *Tests:* daily_test.py and hud_test.py unchanged and passing. *Studio:* paste TycoonCore, playtest.

**L1. Plot frame (nothing visible).** `plotFrame` and every site of section 4.3, all turns 0°; the marked block untouched.
- *Tests:* daily_test.py: `plotFrame` equals today's `plotCenter` for six slots; room, props, hire spots, incubators, both signs and employee facing at 90°, 180°, 270° equal the 0° build turned; fingerprints unchanged; `plotZones` and `CompanyConfig.checkPlacement` identical at every turn. world_test.py follows the text it reads: `plotCenter` and the landing line (:900-913), and "the front is +Z" (:447) becomes "the frame's +Z".
- *Mutants:* IPO sign offset not turned; employee facing ignores the turn; turn sign flipped; `PlotVisuals.check` in world axes.
- *Studio:* paste five scripts, hash block, playtest: nothing moved.

**L2. Permanent, closed building (still the row, still auto-assign).** Section 2.2; `PlotBuilding`, `PlotBuildingVisuals`, `BuildingClient` (at the root), `tools/building_test.py`; first `git apply --check`; inside check in the garage frame; solid outer walls; the new CLAUDE.md and PLOT_VISUALS.md rule.
- *Tests:* building_test.py on `main`, its two base checks on the merge base, its path checks (:1144, :1293-1294) on the root; section 3.4's test; the root scans (section 3.1); inside check and apron at four turns; daily_test.py's wiring list gains three scripts. world_test.py's `makePart(folder, "Floor", ...)` reads (:630, :903) and hud_test.py's mutant anchor on `local floor =` (`AFTER_PLAYERDATA`, :1782) follow the `Floor` into `buildGarages`. The reset restyles to stage 1 and leaves one label.
- *Mutants:* client check in world axes (caught at 90°); apron on the wrong side; section 3.4's set; a label per owner; no reset on leave.
- *Studio:* create three scripts, paste TycoonCore, preview, section 3.4's walk, Test > Device. Can ship alone.

**L3. The claim (behind `ClaimEnabled`).** New `LobbyConfig` (ReplicatedStorage: garages, `PlazaSpawn`, distance, texts, `ClaimEnabled`, a pure `canClaim(state, userId, slot, rootPosition, now)` tested like `CompanyConfig.checkPlacement`). TycoonCore: `onPlayerAdded` split (plaza marker before the first yield, the :874-878 guard on it, first-spawn fallback, cap and startup warning), `claimGarage` with the marked block, states, prompts, the `UserId` hold, the Free room in the reset. ShopServer: receipt deadline from the claim, the door message. IpoClient :695 and :38-42, ShopClient :1589. New `LobbyClient` (by hand): banner, arrow, Robux buttons greyed.
- *Tests:* new `tools/lobby_test.py` (fake players, DataStore, scheduler): section 2.1's compare and run; the four states; one claim per `UserId`; rejoin during Closing; two claims in one tick; distance (far, NaN, infinite, no character); bad slots; leave during load frees and saves nothing; failed load kicks and frees; `ClaimEnabled` off: auto-claim and teleport, and with no Free garage, wait then kick after 60 s; the cap kicks only above the garage count; `#LobbyConfig.Garages == MAX_PLOTS`; first-spawn fallback; a receipt before the claim waits, then is granted once. hud_test.py: the function list (:1510), order checks (:1543-1572), `REFRESH_SIGN_SITES` (:1365), the re-read wait (:1621, :1629) and the mutant anchors (:1779-1783; :1801 on the exact `PlayerRemoving` text) move to `claimGarage` and the new handler, plus "`leaderstats` made there, not on join". world_test.py's E2 anchor (:1418, :1582) follows `Players.PlayerAdded:Connect(onPlayerAdded)`. shop_ux_test.py learns the door toast (:2806) and the claim texts sent through `ShopServer.notify` (:2811); its ScreenGui scan (:2691) covers `LobbyClient`. daily_test.py :7028 and :7040 stay.
- *Mutants (about 20):* section 2.1's set; no one-claim check; claim keyed on `Player`; claim released before the leave save returns; a yield between check and write; plaza marker after a yield; `data.ready` before `refreshSign`; `leaderstats` on join; no distance check; prompt on for a Taken garage; no reset on leave; kill-switch path without teleport; cap kicks at 6; receipt deadline from the join.
- *Studio:* create two scripts; Test > Clients and Servers with 2 and 3 players: claim one garage each, leave and rejoin at once, late join, a returning save in a different garage, the banner at phone size, no infinite-yield warnings. Then turn `ClaimEnabled` on (a publish).

**L4. Ring and plaza.** `LobbyConfig.Garages` gets the ring; `WorldVisuals` the ring layout and its TycoonCore hook in `pcall`; garage shells `Persistent`; the row patch marked superseded.
- *Tests:* world_test.py builds the ring from `LobbyConfig` with every named check: keep-outs for each full lot and its `plotReach` (WorldArt.lua:52), the lounge, the drop spot, the moved spawn pad; gaps of at least 6; lanes clear; building sizes from 62 x 62 to 82.6 x 86.6; `MAX_PLOTS` still copied (:435). render_previews.py draws a top-down SVG.
- *Mutants:* two lots overlapping; a corner gap under 6; a path through a doorway; a lot off the Baseplate; spawn pad covered; a garage facing away.
- *Studio:* **move the SpawnLocation by hand** to (0, 0.5, 175) (the preview prints whether it matches), check the default camera, walk to each garage on a phone, watch streaming.

**L5. Docs and publish.** CLAUDE.md, ROADMAP.md status, README rows, PUBLISH_RULES section 1 ("6 = the garage count"). The section 4.4 checklist, the pre-publish list, publish with **Shut down all servers** (old servers run the old flow).

## 6. Open question for the owner

1. **Respawn after a reset: plaza or own garage door?** *Recommended: own door* (today's hook, less walking). **Decided (2026-10-16, OWNER DEFAULT): own garage, today's hook (`teleportToPlot`), built on branch `lobby-all`.**

The first draft's questions 2 to 7 are decided (top of this file).

## 7. What I did not verify

- **Nothing was run:** no test, no Luau, no Studio. I read code and docs and used git to compare branches.
- **Max Players 60** is the owner's report; the 6 comes from the docs.
- **StreamingEnabled** being on, and its radii.
- Server-side ProximityPrompt distance checks; `Popper`'s 0.25 rule and `CanQuery` needing `CanCollide` off; setting `ModelStreamingMode = Persistent` from a script; DataStore read times; the sign of a turn in Roblox (tests pin it).
- When Roblox retries a `NotProcessedYet` receipt, and whether it limits a `ProcessReceipt` callback that waits for a claim.
- Whether building-pass's patch applies to `main`'s TycoonCore, and whether its tests pass there.
- Part counts for the new-player room and the plaza: estimates from the docs.
- The HUD's empty states for an unclaimed player, beyond the two `leaderstats` waits.
