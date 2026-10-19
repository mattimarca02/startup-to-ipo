# Overhaul 2 plan: a real economy, a real office, things to do

Written 2026-10-19 by the owner session ("Claude (owner session 2)", Claude Code in VS Code, Studio MCP on the place *Build your Startup!*). The brief is the owner's feedback of 2026-10-19 after playing (points 1 to 15) and his addendum of the same day (points 16 to 18). Lanes stay paused (docs/lanes/owner.md). Every phase below is one branch and one pull request; the phases are stacked (each branch starts from the one before it when that one is not merged yet).

The owner's written OKs given in the brief, used by this plan: change economy numbers players already have (point 13); change tests and CLAUDE.md rules that only pin the old look, layout, stage count or economy numbers (each change is listed in its PR and in CLAUDE.md). Not covered, so never done: anything inside the CLAIMLOAD block (if the economy needs it, stop and ask), the DataStore name or key, Robux prices, product or pass IDs, FR-13, a Publish.

## 0. Phase 0: what was found (2026-10-19)

- `main` at `d91f670`; PRs #61, #62, #63 are merged (#64, the ux lane's tap targets, is open and not needed).
- **Studio check (hash of every script, through the MCP):** 35 of the 37 scripts in Studio matched `main` (overhaul 1, #55 to #60, and Batches 1 and 2 are in). Two were behind: `TycoonCore` (PR #61, the welcome-back pop-up) and `EmployeeClient` (PR #63, the hatch reveal holds `OpenPanel`). Both were pushed through the MCP and hash-checked: **all 37 match `main` now**. `IconArt` and `IconVisuals` are not in Studio on purpose (nothing requires them). The place is the published *Build your Startup!* (PlaceId 86395856666175), not a Place1 file.
- **One-player playtest:** spawn on the plaza, walk to Garage 1's post, hold E: the claim works, the owner's save loads. The test save has done 1 IPO and has a valuation of **$1.9M against an IPO-ready of $202K**: the offline pay at the load (50% of Income for up to 8 h, all counted as valuation) jumped it from the Garage straight to stage 5, so the building went from the Garage to Big Corporate with nothing in between. **That is the cause of point 11** ("at Seed I got the Big Office"): the building follows the valuation, and offline Cash, Cash packs and big call rewards can skip whole stages.
- Studio still says Max Players is 60 (must be 6, by hand). Output: no error from our scripts, only Roblox's own UIBlox warnings.

## 1. The new economy (point 13, with points 9, 12, 16, 17)

### 1.1 The ladder

| Stage | Valuation to reach it | Building it unlocks in the shop | Target: first run, active play, reached at |
|---|---|---|---|
| 1 Garage | 0 | Garage (free, the start) | 0:00 |
| 2 Seed | $30K | Small Office | 1:00 to 1:15 |
| 3 Series A | $10M | Big Office | about 3 h |
| 4 Series B | $100M | Small Corporate | 6 to 8 h |
| 5 **Series C (new)** | $300M | Big Corporate | about 12 h |
| 6 IPO-ready | $1B | **HQ Tower (new, sixth building)** | about 20 h |

- Valuation stays "Cash earned in this run" (IpoServer is the only writer, as today). Going public stays at the last stage.
- **Later runs are faster through the IPO multiplier and what is kept** (employees, workstations, perks), so `StageGrowthPerIpo` drops from 2.5 to a small growth (first guess 1.15: the thresholds of run 2 are 15% higher, the multiplier x1.5 and the kept team make it about 2.5x faster). The sim sets the final value.
- **Offline Cash stays** (50% of Income for up to 8 h, the owner's D-C decision), but **only 10% of it counts toward the valuation**: `TycoonCore.addEarnings` already knows the load's offline pay (it is the only earning before `data.ready`), so this is a change outside the CLAIMLOAD block. Cash packs count toward the valuation only up to the same share. So Cash can still buy things, but a login or a purchase can no longer jump stages.
- **The building is the player's choice:** reaching a stage unlocks the next building in SHOP > Office; it never changes by itself (point 12). Its price is a share of that round's threshold (first guess: Small Office $12K, Big Office $3M, Small Corporate $25M, Big Corporate $70M, HQ Tower $250M). The room and the building follow the building **owned**, never the valuation (this ends point 11 for good).
- **The stage-to-building mapping is 1:1 and pinned by a test** (stage n unlocks building n; a building is never more than one step above the last one owned; the IPO resets to the Garage).

### 1.2 What the player spends on, per stage (first-pass numbers; final ones from `tools/economy_sim.py`, written in docs/ECONOMY.md)

Income = (catalog items x the building's office multiplier + employees x the building's team multiplier) x the IPO multiplier x passes. Every item's payback is set so each stage lasts its target time; the stage's own items take about 60 to 80% of what the player earns in it.

| Stage | Catalog items (point 16) | Item prices | Building | Workstations (point 9) | Eggs |
|---|---|---|---|---|---|
| Garage | 11 (Desk, Coffee Machine, Second Monitor, Laptop, Router, Better Chair, Mini Fridge, Server Rack, Whiteboard, Bookshelf, Neon Logo) | free to about $10K | free | 1 free + desks 2 and 3 ($2K, $8K) | Garage Egg about $1.2K (the free egg first) |
| Seed | 11 (standing desks, team table, meeting corner, phone booth, plants wall, ...) | $15K to $2.5M | Small Office $12K | desk 4 ($60K) | + Startup Egg about $40K |
| Series A | 11 (meeting room, QA lab, design studio, server racks, snack bar, ...) | $2.5M to $25M | Big Office $3M | desk 5 ($1.5M) | + Unicorn Egg about $2M |
| Series B | 11 (data center room, marketing floor, recruiting office, lounge sofas, ...) | $12M to $60M | Small Corporate $25M | (base desks full) | |
| Series C | 11 (cafeteria, gym, rooftop terrace, legal office, demo stage, ...) | $30M to $180M | Big Corporate $70M | | |
| IPO-ready | 8 (boardroom, trading screens, press room, executive floor, ...) | $150M to $700M | HQ Tower $250M | | |

- **63 items.** Each gives something real: an income boost, a faster or better founder activity, or a new founder activity (the Server Rack unlocks the production bug; the Router makes calls pay more; the Second Monitor speeds the coding sprint). No item adds workstations: that is the desks' job (below), so the Extra Employee Slots pass keeps its exact value.
- Items unlock at their stage (locked ones shown greyed: "Unlocks at Series A"). Any order inside the unlocked stages (the old "buy in order" rule only stays for nothing: the Garage's first item, the Desk, is still free and first).
- **Saved in the existing `owned` list:** it is provably safe for older code (every version back to the rollback floor M4 loads every name in `owned` and writes every name back; checked in `73d2407`), and it already resets at an IPO, like today's upgrades. The six old upgrade names (Desk, Coffee Machine, Laptop, Server Rack, Whiteboard, Neon Logo) stay as they are: nobody loses one.
- **Workstations (desks, point 9):** a workstation is a desk, a chair and a computer at a hire spot. The team's size is the number of workstations: 1 free, desks 2 to 5 bought with Cash (base total 5, as today's 5 base slots), +3 free with the Extra Employee Slots pass, +1 free per level of the Extra Desk IPO perk (up to 3): 11 at most, the 11 hire spots. **The pass never loses value:** it is +3 free workstations on top, exactly as today's +3 slots. Bought desks are kept through an IPO (like the employees who sit at them), in a new section `office` (section 4).
- **Buy a worker directly (point 17):** a Hire tab with the common and uncommon creatures, each a fixed creature for a fixed price (no roll, so FR-13 is untouched), priced at 4x the expected egg cost of a hire of that rarity, with the comparison on screen ("A Garage Egg gives one for about $X on average"). Needs a free workstation. Server checks price, Cash, workstation, rate.
- **Creature incomes are rescaled** (Common 1, Uncommon 2 to 3, Rare 5 to 6, Epic 13 to 15, Legendary 38 to 40 base) and multiplied by the building's team multiplier (x1 Garage up to x90 HQ), so a hatched employee matters at every stage. Existing employees are kept (only their per-second number changes).
- **Paid items (Robux prices and IDs never change):** 2x Cash and VIP keep their multipliers (still fair: they scale with income). The Cash packs already pay minutes of income; their fixed floors ($250 / $2.5K / $15K) are replaced by floors that scale with the stage (a share of the next round's gap), so a pack bought at Series B is not tiny. Extra Employee Slots: +3 free workstations (unchanged value). Shareholder, Auto-Hatch, Headhunter, Luck Boost, Instant Hatch, Poach Shield: unchanged. The full change list for the owner goes in the phase 1 PR and docs/ECONOMY.md.
- **Daily rewards and onboarding goals rescaled:** Cash days stay "minutes of income" with a stage-scaled floor; the goal chain's stage goals read the new thresholds (they already read IpoConfig); new goals for the first workstation, the first catalog item of each stage and each building.

### 1.3 Existing saves (the migration)

Nobody loses a building, an employee, Cash or Shares; no demotion of owned things.

- On the first load under overhaul 2 (no `office` section yet): the player gets **the building their old stage showed** (the stage of their valuation under the old thresholds, read from a frozen `IpoConfig.LegacyStages` copy), written to `pokedex.active.building` (the existing place for it: CompanyConfig's loader already carries `building` 1 to 99 and keeps unknown values); and **4 bought desks** (today's 5 base slots), so their team keeps its size. Cash, Shares, employees, perks, the IPO count and the valuation are untouched. A valuation that maps to a lower stage under the new thresholds keeps the higher building and every owned item; only what can be unlocked next follows the new ladder.
- The `office` section then marks the migration as done (`migrated = 1`), so it never runs twice.

## 2. Founder activities and calls (points 6, 10, 14, 18)

All server-authoritative, phone-friendly, rewards in seconds of Income paid through `core.addEarnings` inside TaskServer's reward budget (one budget for calls and activities), never a random Cash stake (D9).

| Activity | Unlocks | What the player does | Reward |
|---|---|---|---|
| Customer calls (live) | the first desk (the Desk item) | a call rings; the answer buttons show **above the desk** (a BillboardGui on the desk with two choices); answering walks the character to the desk, sits, plays a 3-second answer animation, then the result | today's row (7 s of Income, chain) |
| a. Coding sprint | the first desk | at the desk: a 20 to 30 s timing mini-game (stop the marker in the green zone, 5 rounds); ships a feature | 20 to 35 s of Income by score; cooldown 3 min |
| d. Whiteboard brainstorm | the first hire | at the blackboard: pick 1 of 3 product ideas, each a different temporary boost (+20% calls for 3 min, +15% Income for 2 min, faster sprint) | a boost (one at a time, not saved) |
| c. Production bug | the Server Rack | an alarm rings; run to the rack and press 4 buttons in the order shown before 20 s | success: 25 s of Income; failure: costs 10 s of Income (never below 0 Cash) |
| b. Investor pitch | every funding round (Seed and up) | 3 multiple-choice questions | each good answer adds a round bonus (40 s of Income each); never blocks the round |
| VIP Investor dinner (point 18) | VIP pass, once a day | a short pitch in the VIP Lounge | 120 s of Income |

- **Calls go live:** the "economy core" that `TaskConfig.StudioOnly` waits for is built in phase 3: the kind-aware earnings path (offline and packs at 10% of the valuation, section 1.1), the daily engaged cap (full value for 3 engaged hours a day, then 25%, on the existing `tasks.engagedDay`/`engagedSeconds`), the rejoin no longer refills the reward bank, then `StudioOnly = false`. Server grading, the rate limits, the anti-spam flags and quiet mode stay as they are. Gate G1 (the owner's D-A) is replaced by this brief's explicit request to turn calls on; the stats line stays so G1's numbers can still be read live.
- **The blackboard (point 10):** the "Next: Desk $0 Buy it in SHOP > Office" sign at the entrance goes; a big blackboard on the office's back wall shows the next steps as chalk bullet points (Enum.Font.IndieFlower, the cleanest of the handwritten fonts), written by the server from the goal chain.
- **No dead time over 2 minutes in the first hour:** checked with the sim's first-hour timeline (every 2-minute window has a purchase, a hatch, a call, a sprint, a brainstorm or a bug).

## 3. Looks (points 1 to 5, 7, 8, 15, 16, 18)

- **Entrance arch (1):** a Roman triumphal arch in white marble at human scale for its role (about 40 studs wide and 34 high: a central archway 12 wide and 20 high, two side passages, four engaged columns with bases and capitals, an entablature, an attic with "BUILD YOUR STARTUP" in a clean serif (SurfaceGui, Enum.Font.Garamond or similar), steps; Marble material, solid boxes only on the piers.
- **Plaza (2):** a real fountain (a round basin with a moulded rim, a two-tier centre with water parts, splash particles, a soft sound), benches that face the fountain and the paths at 5-stud character scale (seat 2 high), lamps 10 to 12 high, planters along the paths; every piece with a purpose, nothing random on the lawns.
- **Join cinematic (3):** a 7-second camera flight over the plaza (arch, fountain, garages) that lands behind the player's character; a tap skips it; once per session; client only.
- **FREE label (4):** the claim post's BillboardGui with `AlwaysOnTop` goes; the text "FREE OFFICE · walk here to claim" sits on a sign board on the post (a SurfaceGui on a part, occluded like normal geometry).
- **Collision in the garage (5):** one invisible anchored box per furniture piece (desks, chairs, props, catalog items), inside its footprint; aisles, the door lane and the spawn stay walkable (tested like the plaza's Solid group).
- **Employees sit at their desk (8):** a hatched employee walks to its workstation, sits and works there (a small typing bob), no wandering.
- **Egg hatch (7):** a new reveal per rarity (common 2 s and simple; legendary about 6 s with light rays, particles, camera shake and a built-in `rbxasset://sounds/` sound), a better egg (oval shape from parts, shading, rarity colors and patterns). FR-13 untouched (the roll is the server's; restricted players get the fixed order); no odds text beyond the real one.
- **Catalog items in the office (16):** each item appears where it fits (a spot list per item: a desk top, a wall, a corner, a side room in the building's band), kit pieces or Parts, with its collision box, never in an aisle or the lane.
- **VIP Lounge (18):** sofas, a bar, lights and a view of the plaza at human scale; a podium with the VIP's rarest employee and a wall board with their company name and valuation, visible through the glass to everyone; the Investor dinner activity inside. Non-VIPs still see in and get the pass offered at the door.
- **Buildings (15):** better materials and depth on facades and interiors, the sixth building (HQ Tower), MeshPart RenderFidelity checked, textures through materials only; the part budgets rise only as far as phone frame rate allows (measured).

## 4. Save sections

| Section | Shape | Why a new section |
|---|---|---|
| `office` (new, rule A10) | `{ v = 1, desks = n (bought, 0 to 4), migrated = 1 }` | workstations bought, kept through an IPO; the migration mark |
| `founder` (new, rule A10) | `{ v = 1, run = ipoCount, pitched = { [stageKey] = true }, dinnerDay = n }` | a round's pitch is offered once per round per run; the VIP dinner once per day |
| `owned` (existing list) | more names (the catalog) | provably safe back to M4 (section 1.2) |
| `pokedex.active.building` (existing field) | 1 to 6 | the building bought this run (the loader already keeps 1 to 99) |

Both new sections: in `KNOWN_SECTIONS`, optional on load (a missing one is a new player or a pre-overhaul save), their own `serialize`, unknown fields kept and written back, bad values skipped with a warning. They are read **after** the CLAIMLOAD block (the block is not changed): `saved` is still in scope there, nothing yields between the block's end and their setup, and `save()` waits for them. A publish with these needs **Shut down all servers** (docs/PUBLISH_RULES.md).

## 5. Phases (one branch and one PR each, in this order)

| Phase | Branch | Owner's points | What |
|---|---|---|---|
| 1 | `overhaul2-phase1` | 11, 12, 13, 16 (data and shop), 17 | the six-stage ladder (Series C), the economy retune with the sim, the catalog (63 items, effects, unlocks) and the shop's Office tab by stage, buildings bought in the shop, the HQ Tower (sixth building and room, valid at every rule), the migration, offline and packs at 10% of the valuation, Cash packs and daily floors, the goal chain, direct hires; docs/ECONOMY.md |
| 2 | `overhaul2-phase2` | 5, 8, 9, 16 (in the room) | workstations (the `office` section), employees sit at their desk, collision boxes per furniture piece, catalog items placed in the office; plus the Studio-only Reset my save (owner, 2026-10-19). **Done: PR #66** |
| 3 | `overhaul2-phase3` | 6, 10, 14 | the economy core and calls live, the answer at the desk, the four founder activities (the `founder` section), the blackboard. **Done: PR #67** (the blackboard hangs over the lane where the old sign stood, facing the spawn: every back wall has windows or decor; the pitch is at the founder desk) |
| 4 | `overhaul2-phase4` | 7 | the egg and the hatch reveal. **Done: PR #68** |
| 5 | `overhaul2-phase5` | 1, 2, 3, 4, 18 | the Roman arch, the plaza and fountain, the join cinematic, the FREE sign, the VIP Lounge and the Investor dinner |
| 6 | `overhaul2-phase6` | 15 | buildings and interiors quality, the HQ Tower's detail, frame rate on a phone |
| end | | | docs/OVERHAUL2_REPORT.md, ROADMAP Status, CLAUDE.md, the publish checklist |

After each phase: every test suite one at a time (fixed or updated), the changed scripts pushed to Studio through the MCP and hash-checked, a playtest (1 player; 2 players with Test > Clients and Servers when the plaza or the claim changes; Test > Device for UI, by the owner when the MCP can't), the Output read, a PR (what changed, rule changes, tests, Studio steps, not tested), a batch in docs/STUDIO_SYNC_BATCH.md, and an Italian summary for the owner.

## 6. Risks and what this plan does not promise

- The MCP drives one client and its screen captures came back white last time: looks are checked from data and the owner's eyes; 2-player and phone tests are listed for the owner when the MCP can't run them.
- 20 hours of first run is a sim number for a perfect active player; real players are slower. The sim and its assumptions are in docs/ECONOMY.md.
- Part budgets: more furniture, collision boxes and a sixth building cost parts; every budget rise is measured (Stats, FPS in Studio play) and written down.
