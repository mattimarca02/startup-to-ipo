# Overhaul plan: from "works" to "a game you want to play for an hour"

Written 2026-10-18 by the owner session (Claude Code in VS Code, Studio MCP connected, lanes paused: docs/lanes/owner.md). Phase 0 of the owner's brief: what is wrong today, what the first 30 minutes should feel like, and the phases that get there. Every phase is one branch and one pull request; claims are in docs/lanes/claims.md as "Claude (owner session)".

## 1. What is wrong today (audit of 2026-10-18)

How it was checked: `main` at `e8bb44a`, the Studio place in Team Create, a one-player playtest through the MCP (spawn on the plaza, walk to Garage 1's post, claim with E, the garage's data read on the server), a hash check of every script in Studio against the repo, and the eight test suites. Two-player tests and the phone view were **not** run (the MCP drives one client; Test > Device is by hand). The MCP's screen capture gave one usable frame (the plaza at spawn) and then only white frames, so looks were judged from the data (part counts, positions, flags) and from the owner's report.

### The owner's seven points, confirmed

| # | Point | What the code does today | Fix in |
|---|---|---|---|
| 1 | Looks like a game built in one second | The world is 336 flat colored Parts on a plain green Baseplate (Plastic, no texture): paving slabs 0.16 high, ball trees, block benches. The six garages are 1,392 parts (a kit shell of 88 parts and a 138-part "free room" each). Studio already has a Sky, Atmosphere, Bloom, SunRays and ColorCorrection; Lighting.Technology is not readable from a script (set by hand). | Phases 2 and 5 |
| 2 | You walk through benches and trees | Every World part has CanCollide off by design (`WorldVisuals`: "the paths are thin colored layers on the Baseplate, which stays the only solid ground"). Nothing on the plaza is solid. | Phase 1 |
| 3 | From inside, the garage is invisible | `BuildingClient` fades the **whole** shell (walls, roof, windows, the sign) to Transparency 1 as soon as the player is inside or on the apron, so inside you see only the room's low walls (6 studs) and no ceiling; the building exists only from outside. | Phase 2 |
| 4 | Tables before anyone is hired | `PlotVisuals.buildRoom` builds a hire desk at every one of the 11 hire spots in every room (`art.Layout.employeeSpots`), owner or not: the free garages show 11 crates, a claimed Garage shows 11 crates with nobody at them. | Phase 3 |
| 5 | No meaning: what, why, what's next | The first minute (free egg, arrow to the sign, two goals: Hire 3, Reach Seed) exists, but there is no story, the goal chain is off (`OnboardingConfig.ChainEnabled = false`), the goals say what but not why, and after Seed nothing tells the player what the IPO is for. The six upgrades cost 0 / 25 / 100 / 400 / 1,500 / 5,000: the whole Garage shop is bought in about five minutes, then the only purchases left are eggs (250 / 2,500 / 25,000) and HR levels until the first IPO at 10 to 15 minutes. | Phase 4 |
| 6 | Other garages still show FREE after you claim one | The FREE sign (a BillboardGui on each claim post), the green lamp and the "Claim garage" prompt are **server** objects, shown to everyone; `LobbyClient` hides only its own banner and marker (`Garage ~= 0`), `ClaimButtonClient` only its button. The server refuses a second claim ("You already have a garage"), but the owner still sees five FREE posts. | Phase 1 |
| 7 | The empty sign with the arrow at the entrance | PR #36 put a sign board over each Garage's door (`PlotBuilding` `sign`): a plate, a dark board and three accent bars (a growth-chart emblem, no text: building_test pins "signs are Parts only, no text, no decal, no gui"). It names nothing and does nothing. | Phase 1 |

### Found during the audit

- **A1. Studio is behind `main`.** Four scripts in Studio differ from the repo (DailyConfig, DailyServer, OnboardingClient, OnboardingServer: PRs #51, #52 and #53 were merged but never pasted) and two are missing on purpose (IconArt, IconVisuals: "paste later", nothing requires them). Batches 1 and 2 of docs/STUDIO_SYNC_BATCH.md say "Run on: (not yet)" but Studio has the claim on, the ring, the SpawnLocation on the plaza and the nine Batch 1 scripts: they were run and not written down. Phase 1 syncs the four scripts and writes the batches as run.
- **A2. Max Players is 60 in Studio** (the server warns at start: "Max Players is 60 but there are 6 garages"). It must be 6 (docs/PUBLISH_RULES.md section 1), by hand: Studio **File > Game Settings > Places > Max Players = 6** (and in Creator Hub for the published place).
- **A3. A `Clouds` object sits under `Lighting.Sky`** instead of `Workspace.Terrain`, so Studio prints "Cloud instance must exist under Terrain node in workspace to be visible" twice per session and no clouds show. Phase 1 moves it (a Studio object, not a script).
- **A4. The fade's apron fades the whole facade** as a player walks up to the door (the brief's point 3 from outside: the building "blinks" when someone comes near it).
- **A5. No interior light in the buildings** (`PlotBuilding.Budget`: "no lights"); the room's 2 or 3 PointLights are the only light, and the roof blocks the sun once it stays visible (Phase 2). Phase 2 allows one interior light per building.
- **A6. Nothing marks "your" garage** from the plaza but a name 12 studs over the roof (`GarageSign`, a BillboardGui, only while the owner plays) and the World's number sign. After the facade sign gets text (point 7), the name is on the building itself.
- **A7. Calls are Studio only** (`TaskConfig.StudioOnly = true`, decided: they stay off until the economy core). In Studio the "Answer" chip rings for a player with an IPO; live players never see it. The first-hour design assumes calls; without them the first hour is purchases, hatching and waiting. Phase 4 plans around that (the goal chain's call goals are skipped off Studio, never blocking).
- **A8. The stage 1 room has 258 parts** (budget 260), so Phase 3's desks-on-hire frees about 11 kit pieces per room, and Phase 5 has no room budget left for richer interiors unless the budget rule changes (it will: 320 per room, measured on a phone).
- **A9. The claim post's prompt reads "Garage N"** (`ObjectText`), the World's number sign reads "N": fine, but the player never learns why they should pick one garage over another. Phase 1 makes the facade sign say "FREE" on a free garage and the owner's company name on a taken one.
- **A10. Lighting is already set up in Studio** (Sky `rbxassetid://6444884337`, Atmosphere density 0.3, Bloom 0.6 at threshold 1.6, ColorCorrection warm tint, SunRays 0.01, DepthOfField off, ClockTime 14, Brightness 3): good base. Only `Technology` (ShadowMap or Future) is unknown and is a by-hand setting.

### Not verified

- Two players (claim, FREE signs from the second player's side, the leave and the reset): needs Test > Clients and Servers by hand.
- The phone layout (Test > Device): by hand.
- Looks: no screenshots after the first (the MCP capture returned white frames in play and in edit mode). The owner judges looks from Studio; this plan judges them from the data.

## 2. The target: the first 30 minutes, minute by minute

Assumes a brand-new account, a phone or a PC, calls off (live). "You" = the player. The numbers are today's prices unless Phase 4 says otherwise.

| Minute | What happens | What you see and feel |
|---|---|---|
| 0:00 | Spawn on the plaza. A short welcome card: "You're a founder with an idea and no money. Claim a free garage, hire a team, grow, raise funding, go public." The nearest FREE garage has a green marker and its facade sign reads FREE. | The place looks like a real campus: paved plaza, lawns, trees you can't walk through, lamps, six buildings with signs. |
| 0:20 | Hold "Claim garage" (or tap the big green button on a phone). The sign over the door changes to "<Your name>'s Startup · Garage". The other FREE signs, lamps and prompts disappear for you. You land inside: brick walls around you, a ceiling with a bare bulb, the roll-up door open onto the plaza, one old desk, one chair, an old PC, a phone, junk. No empty desks. | "This is my garage." |
| 0:30 | Toast: free Garage Egg incubating (60 s). The arrow points at the shop sign: "Next: Desk · free · SHOP > Office". You open SHOP > Office and take the free Desk: the desk prop pops in, +$1/s shows on the bar. | First purchase inside 30 seconds, as the M5 goal says. |
| 1:00 | The goal card shows two goals with a reason each: "Hatch your first hire (an employee earns while you're away)", "Own 3 upgrades (each one raises your income)". Coffee Machine at $25 is affordable around 0:50. | Always one obvious next step. |
| 1:30 | The egg is ready: the arrow moves to the incubator, "Hatch". A creature walks in, a **desk, chair and computer appear at its spot** with a pop, a ghost desk marks the next spot. | The office starts to fill. |
| 2:00 to 5:00 | Laptop $100, Server Rack $400, a second Garage Egg $250, Whiteboard $1,500. Each purchase pops its prop in. Seed ($1.8K valuation) lands around 4 to 5 minutes. | A purchase every 40 to 90 seconds. |
| about 4:30 | **Seed.** The stage-up moment: a flash and sparkles over the plot, a toast "Seed round raised! Your garage becomes a Small Office", a short sound, the building visibly swaps to the white Small Office with its door and windows, the camera gives a one-second look at the new facade. The goal card moves on: "Reach Series A ($6.3K)", "Hire 3 employees". | The first reward you can see from the plaza. |
| 5:00 to 10:00 | Neon Logo $5,000 around 6 to 7 minutes (the last upgrade), the Daily gift opens by itself at the first pause after the third hire (Day 1: 5 min of income, at least $300), Series A ($6.3K) around 8 minutes: the two-story Big Office. Startup Egg ($2,500, 5 min) affordable. | The office grows with the company: 3 hires, 3 desks, the building changed twice. |
| 10:00 to 15:00 | Series B ($23.4K): the four-story blue glass Small Corporate. Goals: "Hire 5", "Reach IPO-ready ($81K)". HR Department levels in the Poach window if another player is in the server. | Every stage is a bigger building you walk into. |
| 15:00 to 25:00 | IPO-ready ($81K): the tower. The IPO button pulses, the sign reads GO PUBLIC. The IPO window explains the trade: Cash and upgrades reset, employees and perks stay, x1.5 income and 10 Shares. You go public: the bell, the tower resets to a Garage with a "fresh start" flash, the Shares shop opens (Faster Recruiting 5 Shares). | The loop closes: "I start again stronger." |
| 25:00 to 30:00 | The second run: the Garage shop again at x1.5 income, Seed in about 3 minutes, the next IPO in sight at about 2.5x the thresholds. A second player in the server: poaching and HR become a thing. | A reason to come back tomorrow: Day 2 of the calendar, the next IPO, the next perk. |

Dead time rule: never more than 2 minutes without something to buy, hatch, or reach. The longest wait today is the Neon Logo ($5,000 at about $200/s = 25 s) and the eggs' timers (60 s, 5 min): fine. The real gap is **meaning**, not pacing.

## 3. The phases (adapted to the audit)

Rules for all phases: the repo is the source of truth (every changed script pushed to Studio through the MCP, hash-checked); the eight suites run one at a time (`LUAU=~/.local/luau-dl/luau`); never a save-format, DataStore, purchase, server-authority, claim, CLAIMLOAD or gameplay-position change; Max Players stays 6; `LobbyConfig.ClaimEnabled` stays true; built-in Parts, materials, lighting, effects and the kit only; never Publish; no breakpoint left before a playtest.

### Phase 1: bugs and basics (branch `overhaul-phase1`)

1. **Sync Studio with `main`:** paste DailyConfig, DailyServer, OnboardingClient, OnboardingServer (PRs #51 to #53); hash check `ALL OK`; write Batches 1 and 2 as run (with what was skipped).
2. **FREE only for players without a garage (point 6):** `LobbyClient` hides, on this client only, the FREE BillboardGui, the lamp and the claim prompt of every garage while `Garage ~= 0`, and shows them again while `Garage == 0` (the server still decides every claim; a prompt disabled locally never shows).
3. **The facade sign gets text (point 7):** the sign board carries a SurfaceGui the server writes through `PlotBuildingVisuals.setSign(model, title, subtitle)`: "FREE · Claim this garage" on a free garage; "<Owner>'s Startup" and the stage's name ("Garage", "Small Office"...) on a taken one; the emblem stays beside the text. Rule change: a sign may carry a SurfaceGui with text the server sets (building_test's "signs are Parts only" becomes "a sign has one SurfaceGui, text set by the server, no decal"). The old 12-stud BillboardGui name over the roof goes (the sign replaces it).
4. **Collision on the plaza (point 2):** `WorldVisuals` builds a `Solid` group: one invisible anchored box (CanCollide on, CanTouch off, Transparency 1) per tree trunk, bench, lamp post, planter, the fountain's basin and the arch's two posts; nothing on a path, a walk, the spawn pad, the claim posts or the lanes. Rule change in world_test: "every part never collides" becomes "every look part never collides; the Solid group's boxes collide and stand only under decor, never on a path".
5. **Output clean:** `Clouds` moved under `Workspace.Terrain` (a Studio object; the owner saves it); the Max Players note for the owner (by hand).
6. Tests, Studio push, hash check, 1-player playtest through the MCP, PR, Batch 3 in docs/STUDIO_SYNC_BATCH.md, the Italian summary.

### Phase 2: a real building, inside and outside (branch `overhaul-phase2`)

1. **Occlusion fade instead of the whole-shell fade:** `BuildingClient` casts a few rays from the camera to the character every frame (the character's root and head); only the Fade parts those rays hit (and the roof when the camera is above it looking down) go to Transparency 0.75 (glass to 0.85), everything else stays as built; a part no longer in the way comes back in 0.3 s. Outside, nothing fades. The apron rule goes. BUILDINGMATH changes with it (the test compares the two copies).
2. **Inside it reads as a building:** the kit walls have an inner face already; the roof piece (`Floor` key, look "roof") is the ceiling; one interior PointLight per building (budget: 1 light, rule change) warm at stage 1, white at 2 to 5; the room's low walls stay (they are the "interior finish"). Big Office and up keep their ceiling piece.
3. **Stage change is a moment:** server side the swap stays as it is (`syncBuilding`); the client (`BuildingClient`) notices the new `Stage` attribute on its own garage, plays a 2.5-second look (camera tweens to a spot in front of the facade and back, skippable with a tap, never while a window is open), a toast from `IpoServer` ("Seed round raised! Welcome to your Small Office"), the existing flash and sparkles, and a built-in sound (`rbxasset://sounds/electronicpingshort.wav` or similar; nothing from the Store). After an IPO: no cinematic, a "fresh start" flash only (owner rule).
4. Camera: the solid boxes keep CanQuery on (Roblox's camera needs it); the roof box is above 12.5. Checked by walking in and out of every door at every stage with Debug > "Building: next stage".

### Phase 3: the office grows with the company (branch `overhaul-phase3`)

1. **Desks only for hires:** `PlotVisuals.buildRoom` builds no hire desks; `PlotVisuals.setDesks(plot, count)` builds a desk at spots 1..count (the kit `Desk`, `Chair` behind it and a `Computer`, scaled to the desk zone; the Parts version without the kit) plus one ghost desk (Transparency 0.7, no light) at spot count+1. `EmployeeServer.placeEmployees` tells TycoonCore the count through a new `core.onTeamChanged(player)`; a new desk pops in. Derived from `#team.employees` only: nothing saved. The free rooms show no desks.
2. **Upgrades visible:** the six props already pop in on purchase (kept); Phase 3 only checks each is visible from the door and adds a small sparkle on the pop.
3. Rule changes: "a desk for every hire spot" becomes "a desk per hire and one ghost"; the stage 1 fingerprint and the desk checks in daily_test change; the room budget stays 260.

### Phase 4: meaning and the first hour (branch `overhaul-phase4`)

1. **The story:** a welcome card on the plaza (LobbyClient, once per session, dismissible, phone-sized): founder, garage, hire, grow, raise rounds, IPO, start again stronger. The IPO window's first lines say the same.
2. **The goal chain on:** `OnboardingConfig.ChainEnabled = true` (U1 is merged: the card draws only the goals the server shows). Texts rewritten so each says what and why ("Hire 3 employees: each one earns for you"), the call goals stay (skipped off Studio). New goals after Seed: Series A, Series B, IPO-ready, "Go public".
3. **Always one next step:** the goal card, the arrow (kept), and the facade sign's second line mirrors the next goal for the owner. The valuation bar is the progress bar to the next round (kept, it already reads "Garage → Seed · $0 / $1.8K").
4. **Pacing check** with tools/economy_sim.py and the timeline above; any price or number players already have is changed only with the owner's written OK (none planned: the dead-time rule holds with today's numbers).
5. Calls stay Studio only.

### Phase 5: the visual pass (branch `overhaul-phase5`)

1. Lighting: Future (by hand: Lighting > Technology), the existing Atmosphere, Sky, Bloom and ColorCorrection retuned for phones (Bloom size 24, no DepthOfField, EnvironmentDiffuseScale 0.6, shadows on the sun only).
2. Ground: the Baseplate becomes grass-colored Terrain or a Grass-material Baseplate with a darker lawn tint, the plaza paving in Cobblestone/Concrete slabs with kerbs, planters with flowers, lamp posts with glow, trees with two crown sizes; one palette (WorldArt.Palette) shared with the buildings' styles.
3. Buildings: window frames and sills on every stage (Blocks), a canopy over the office doors, pilasters on the Big Office, fins on the glass tower, the podium band; signs with the company name (Phase 1).
4. Interiors per stage: a rug, a plant and a lamp more per stage; the HQ's skyline stays.
5. Budgets: at most 2,600 parts for six garages at the biggest stage plus the world (measured with Stats; FPS reported in docs/OVERHAUL_REPORT.md).

### Phase 6: phone and UI polish (branch `overhaul-phase6`)

Test > Device (portrait 390x844, landscape 844x390): every button reachable, nothing under the thumbstick or jump button, windows fit; pop-ups at the bottom center; one window at a time. Fixes in the clients as found.

## 4. After every phase

Tests one at a time; Studio push and hash check; a playtest through the MCP (one player) and the by-hand ones listed in the PR; the PR body (what changed, rule changes, tests, Studio steps, not tested); a new batch in docs/STUDIO_SYNC_BATCH.md; the Italian summary to the owner; then the next phase on a branch based on the previous one if it is not merged yet.

At the end: ROADMAP.md Status, CLAUDE.md, docs/OVERHAUL_REPORT.md, the publish checklist (Shut down all servers) for the owner's decision.
