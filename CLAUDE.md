# CLAUDE.md: project rules for Claude Code

Read ROADMAP.md first. At the end of every milestone, update its Status section.

"Startup to IPO" is a Roblox idle tycoon, published as **Build your Startup!** (place `86395856666175`, universe `10768772528`). Two collaborators build it together in Team Create. See `README.md` for the file layout and `CONTRIBUTING.md` for the workflow and the Ownership table.

## How to work with us

- We are beginners. After each step, explain what you did in 2–3 plain sentences, then give the exact Studio clicks.
- Report results honestly: if a playtest shows errors or a step was skipped, say so.

## Before changing anything

1. **Read the code you're about to touch** and follow its structure, naming, comment style and save system.
2. **Check the Ownership table** in `CONTRIBUTING.md`. Only edit scripts claimed by the person you're working for. If a script is claimed by someone else, stop and say so.
3. **Work on a branch,** never on `main`, and `git pull` first.
4. **Don't rewrite working systems.** Extend them.
5. **Don't delete anything you weren't asked to delete:** scripts, Studio objects, functions, save fields, config entries or files.

## File structure (keep it)

- One Studio script = one `.lua` file at the repo root with the same name. The README lists where each one goes in Studio.
- **TycoonCore** (Script, ServerScriptService) owns `playerData`, saving and loading, and income.
- **Feature modules** are ModuleScripts in ServerScriptService that TycoonCore requires and plugs in:
  - `Module.init(core)`, where core is `{ getData, save, updateIncome, ... }`
  - `Module.setupPlayer(player, data, savedSection)`
  - `Module.serialize(data)`

  New server features follow this pattern. Never add a second DataStore, save loop or PlayerAdded data owner.
  Current ones: `ShopServer`, `EmployeeServer`, `PoachServer`, `IpoServer`, `OnboardingServer`, `DailyServer` (the daily calendar; its client is `DailyClient`). `DailyServer.setupPlayer` runs last, inside the all-modules-loaded gate, after `EmployeeServer` (a claim can grant an egg). A claim never yields between the "today is free" check and writing `lastClaimDay`.
  `CompanyServer` (the company and its Pokedex: the `pokedex` save section; its client comes later) is customize PR 1 and **invisible to players**: its `init` and `setupPlayer` come after `OnboardingServer` and before `TaskServer` (and `DailyServer` stays last); `setupPlayer` needs `data.ipo` (the run check reads the IPO count). It gets no `addEarnings` and writes only `data.pokedex`: it never touches Cash, Income or the valuation (`tools/daily_test.py` checks all of it). An IPO by this version keeps `run` equal to the IPO count: `commitIpo` calls `CompanyServer.writeIpoRun` inside the IPO's save transform and `CompanyServer.onIpo` only after that save worked (no stamp, no card, no sector completion until the IPO transform of PR 4). While its section is `locked` (a newer `v`, an unknown sector, or one it couldn't read) it writes the section back unchanged and `commitIpo` refuses to go public. Its three requests (`"Place"`, `"Store"`, `"Sync"` on `CompanyRemotes.CompanyAction`) work only in Studio until the office screen exists (`CompanyConfig.Placement.StudioOnly`); Place and Store never save by themselves (autosave does). The rules (checks, limits, the run check, the loader) are pure code in `CompanyConfig`, tested with fakes; docs/CUSTOMIZE_PROPOSAL.md has the plan, docs/CUSTOMIZE_PR1_NOTES.md what PR 1 decided.
  `TaskServer` (the task engine, PR 1: customer calls; its client is `TaskClient`) plugs in just before `DailyServer`: its `init` and `setupPlayer` come after `EmployeeServer`/`IpoServer` and before `DailyServer`. **PR 1 runs only in Studio** (`TaskConfig.isActive()`: `Enabled` and (`StudioOnly` is off or `RunService:IsStudio()`)): outside Studio it builds no remotes, starts no loop and shows nothing. Task Cash is paid through `core.addEarnings`, the one earnings path, and `StudioOnly` stays on until the economy core (PR 2) exists. Only the server grades: the client sends `"Answer"` with a call number and never a time or a reward. `tools/daily_test.py` lists every `addEarnings` call site (it scans every `.lua` file at the root; a new one fails there until it is reviewed) and pins that only `IpoServer` assigns `.valuation`, `.lifetime` or `.best` (DailyServer's `daily.best` is the streak record).
- **Plot visuals** (looks only; docs/PLOT_VISUALS.md): `PlotArt` (the data) and `PlotVisuals` (the builder and the checks) are ModuleScripts in ServerScriptService that TycoonCore requires inside `pcall` and calls through `looks()`. `PlotArt.Stages[i]` is the room of `IpoConfig.Stages[i]`: five rooms (Garage, Seed, Series A, Series B, IPO-ready), the plot stays 60 x 60. Rules: nothing is saved, sent through a remote or read back; a room never moves a gameplay position (hire grid, six upgrade stations, incubators, signs, spawn, 6+ stud aisles: `PlotArt.Layout`, compared with the scripts) and nothing of it stands in a reserved zone; the six upgrade props are one shared list, identical in every room; only shell, floor, walls, door, windows, hire desks and decor change per stage; shells stay open (side walls 6 studs at most, back wall 12, no roof, no front wall); every part is anchored with `CanCollide`, `CanTouch` and `CanQuery` off (the real `Floor` is the only solid); built-in Parts and the allowed materials only, no assets, nothing random, no odds text (D9); at most 260 parts and 3 PointLights per room. Add or change a room in `PlotArt.lua` only, then run `tools/daily_test.py` (stage 1, the props and the layout have fingerprint tests: they fail on purpose if one changes).
- **Configs** are ModuleScripts in ReplicatedStorage:
  - `ShopConfig`: passes, products, `EggsEnabled`, `PolicyCheck` (the paid random items check on join)
  - `CreatureConfig`: creatures, rarities, eggs, odds, slots, poaching rules (`CreatureConfig.Poaching`)
  - `IpoConfig`: funding stages, IPO rewards (multiplier, Shares), cooldown, IPO shop perks
  - `OnboardingConfig`: the new-player free egg, goals, arrow and tracker settings
  - `TaskConfig`: one row per task (arrival gap, time limit, reward in seconds of Income, action, team auto-resolve share, demand per hire, queue cap, skip), the stage-to-rung table, the reward budget, the `Enabled` / `StudioOnly` switches. No text in it may claim odds or chance (D9)
  - `SectorConfig`: the four sector keys (`Software`, `Gaming`, `Fintech`, `Biotech`, never renamed), which can be picked (only Software), `PickerEnabled` (off), the company names, the Hall of Fame goals
  - `CompanyConfig`: the Pokedex format version, the placement rules (buildings and footprints, limits, the one pure `checkPlacement`), the loader of the `pokedex` section (`load`, `toSave`, the run check) and `Placement` (`Enabled`, `StudioOnly`). No text in it may claim odds or chance (D9)
  - `DailyConfig`: the 7-day login calendar (rewards, grace days, reset hour, texts). Daily Shares are granted as they are and are **never doubled** by the Shareholder pass; daily Cash is a gift and never goes through `addEarnings` (it must not raise the IPO valuation)
- **Clients** are LocalScripts in StarterPlayerScripts. They build their UI in code, only display server state, and send requests through the server-created remotes `ShopRemotes` (`ShopAction`: `"Upgrades"` lists the six office upgrades, `"BuyUpgrade"` sends only the upgrade's number; `ShopNotify`), `EmployeeRemotes`, `PoachRemotes` (`PoachAction` also has `"BuyHr"`, with no argument), `IpoRemotes`, `OnboardingRemotes`, `DailyRemotes` (`DailyAction`, only `"Claim"`), `CompanyRemotes` (`CompanyAction`: `"Place"`, `"Store"`, `"Sync"`; Studio only until the office screen exists) and `TaskRemotes` (`TaskAction`: `"Answer"`, `"Skip"`, `"Start"`, `"Pause"`, `"Sync"`; `TaskState` server to client) in ReplicatedStorage.
- **Nothing is bought or opened by touching the world.** The three old walk-on pads are gone: office upgrades are bought in the shop's Office tab (`TycoonCore.buyUpgrade`, the one function; the client sends only the upgrade's number), HR Department levels in the Poach window, and the IPO window opens from the HUD. The garage keeps two non-interactive signs (the next upgrade, the funding stage). Do not add a `Touched` handler that buys or triggers anything (`tools/daily_test.py` fails on one; the VIP Lounge door in ShopServer is the only one).
- **UI conventions:**
  - One window open at a time, using the PlayerGui attribute `"OpenPanel"`.
  - The daily gift chip (DailyClient) is not a HUD slot: it sits right of the valuation bar, which leaves room for it (`IpoClient` `CHIP_ROOM`). Its pop-up goes at -240.
  - The task tray (TaskClient) is not a HUD slot: three 48-high chips at the bottom (portrait: right of the HUD column and above the thumbstick; landscape: between the thumbstick and the jump button). It hides while a window is open. `tools/daily_test.py` checks its layout at both phone sizes.
  - HUD button slots: EGGS 0, SHOP 1, TEAM 2, POACH 3, IPO 4. They use the shared responsive layout: a column centered on the left, or a top row on short (phone) screens (height under 460).
  - Pop-up messages go at the bottom center.
  - Everything must work on a phone.
- **Studio-only debug tools** live in the shop's Debug tab. Add buttons with `ShopServer.addDebugAction`. They must stay behind `RunService:IsStudio()` and `ShopConfig.DebugInStudio`, so they never run on live servers.

## Server authority

- Game logic, prices, timers, random rolls, slots and income all run on the server.
- A client only asks, for example `TeamAction("BuyEgg", 2)`. The server checks everything: argument types, ranges, cash, ownership, and `data.ready`. It refuses anything invalid.
- **Paid random items (FR-13, D9 option B):** `ShopServer.isRandomRestricted(player)` comes from PolicyService on every join and fails closed (error or timeout = restricted for the session). Restricted players never get a random roll (`EmployeeServer.rollCreature` uses the egg's fixed order, `CreatureConfig.fixedHire`) and can't buy items marked `changesOdds` (Luck Boost). A new random reward must follow the same rule.
- **Never trust the client for purchases:**
  - **Game passes:** re-check ownership with `UserOwnsGamePassAsync`.
  - **Developer products:** grant them only in `ProcessReceipt`. This must stay idempotent, using the saved PurchaseId list, and return `PurchaseGranted` only after the save succeeded.
- Client-only visuals are fine as long as they never change data. Examples: employees walking around, the hatch reveal.

## Config-driven items

- Add content by adding config entries, not by hardcoding names, prices or IDs in logic:
  - passes and products in `ShopConfig`
  - creatures, eggs and rarities in `CreatureConfig`
- Never rename or reuse a config key once it has shipped, because saves and receipts refer to keys.
- Pass and product IDs come from `sync_monetization.py`; never invent one. For a new item, add it with `id = 0`, and the owner runs the sync.
- Egg items have `needsEggs = true`. They are only sold while `ShopConfig.EggsEnabled = true`.

## Save format

- DataStore `"StartupTycoon_v1"`, key `"player_<UserId>"`. Never change either.
- The payload is written only by TycoonCore's `save()`:

```lua
{
  cash = number,
  owned = { "Desk", "Laptop", ... },            -- upgrade names
  lastSeen = os.time(),                          -- for offline income
  shop = {                                       -- ShopServer.serialize
    luckLeft = seconds, instantHatches = number,
    receipts = { PurchaseId, ... },              -- last 100, for idempotency
  },
  team = {                                       -- EmployeeServer.serialize
    employees = { { id = GUID, creature = "CodingCat", hiredAt = os.time() }, ... },
    incubators = { false or { egg = "Garage", startedAt, hatchAt }, ... }, -- 3 slots (+ Extra Incubator perk), false = empty
    pending = nil or { id, creature, hiredAt },
  },
  poach = {                                      -- PoachServer.serialize (optional: older saves have none)
    hrLevel = number, shieldLeft = seconds, cooldownUntil = os.time(),
    losses = { os.time(), ... },                 -- recent losses, for the loss limit
    gained = { [employeeId] = { from = UserId, refund } },  -- moves the other save hasn't confirmed yet
    lost = { [employeeId] = { to = UserId, at } },          -- who took our employees (last 30 days, max 50)
    refund = nil or number,                      -- Cash of a negotiation the server stopped during
  },
  ipo = {                                        -- IpoServer.serialize (optional: older saves have none)
    count = number, shares = number,             -- IPOs done, unspent Shares
    valuation = number,                          -- Cash earned since the last IPO (decides the stage)
    lifetime = number, best = number,            -- Cash earned ever; best valuation on any run (leaderboard)
    lastIpoAt = os.time(),                       -- for the IPO cooldown
    perks = { [perkKey] = level },               -- IPO shop perks
  },
  fixedHires = {                                 -- EmployeeServer.serializeFixedHires (optional: written only once used)
    counts = { [eggKey] = number },              -- hires made from each egg's fixed order (restricted players, FR-13)
  },
  daily = {                                      -- DailyServer.serialize (optional: older saves have none)
    lastClaimDay = number,                       -- UTC day number of the last claim (0 = never)
    streak = number, best = number,              -- claims in a row (one missed day keeps the place), longest ever
    claims = number,                             -- total claims
  },
  tasks = {                                      -- TaskServer.serialize (optional: written only once there is something to keep; Studio only in PR 1)
    sharesRun = number,                          -- IPO count a pitch's Shares reward was last used for (later PRs)
    done = number, bestChain = number,           -- calls answered and graded, longest chain
    seen = { [taskKey] = true },                 -- task kinds the player has met
    engagedDay = number, engagedSeconds = number, -- engaged seconds on that 08:00 UTC day (PR 2 caps full-value time with it)
  },
  pokedex = {                                    -- CompanyServer.serialize (optional: older saves have none). Customize PR 1 writes the whole format
    v = 1,                                       -- format version: a higher one is kept opaque and unchanged, and the session refuses an IPO and every change
    run = number,                                -- the IPO count the active company belongs to. An IPO by this version moves it with the count (commitIpo, in the IPO's save and then in memory; no stamp or card until PR 4). Run check on join: run < count = only an older version (before this section) ran an IPO, run > count = a Studio reset
    active = { sector, picked, name, foundedAt, engaged, passSeconds, building, decor, objects = { { id, x, z, r } }, stored, told, rounds, sx },
    sectors = { [sectorKey] = { state, stamp, replays, firstAt, bestEngaged, card } }, -- the four keys are known from PR 1
    kept = { [objectKey] = n }, hall = { [goalKey] = os.time() }, dust = number,
    studio = boolean,                            -- set by any Studio server and never cleared: a Studio save never reaches a live board
  },
  onboarding = {                                 -- OnboardingServer.serialize (optional: older saves have none)
    seenIntro = boolean,                         -- the free egg was given (or wasn't needed): never given twice
    legacy = boolean,                            -- had a save before M5: counts as already onboarded
    arrowDone = boolean,                         -- the glowing arrow did its job (never comes back)
    dismissed = boolean,                         -- the player closed the goal tracker with its X
    goals = { goalKey, ... },                    -- finished goals (stay finished)
  },
}
```

- **Old saves must keep loading.** New fields are optional and get defaults. Bad or unknown values inside a section are skipped with a warning, never an error. Never rename or remove an existing field. **Exception, the `pokedex` section: never delete what you do not know.** Unknown item ids (in `objects` and `stored`), unknown fields and a stored value other than `true` are kept and written back; a shape this version can't carry back (placed items that are not a plain list) keeps the whole section as it was (locked). Only malformed entries (a bad coordinate, a repeated id, an id that is not a short string) and entries over the limit of 40 are skipped, with a warning.
- **Never delete what you don't know.** `save()` writes back every top-level section of the loaded save that this version doesn't recognise (`KNOWN_SECTIONS` in TycoonCore), so older code never wipes a newer section. Eggs saved in incubators above the current count are kept the same way (EmployeeServer `parked`). Code that ran *before* this rule (anything older than milestone 4) can't do this: publish with **Shut down all servers** when a new section is added.
- **Keep unknown fields at every level.** The `pokedex` loader (`CompanyConfig.load`) keeps unknown fields in the section, `active`, `objects[i]`, `rounds[k]`, `sectors[k]`, `card` and every map, and writes them back as they were: copy that pattern for any new section. A saved section with a higher `v` is written back unchanged.
- **New saved data gets its own top-level section (rule A10).** Older code keeps unknown *top-level* sections, but it drops unknown *fields inside* a section it knows (`team`, `poach`, `ipo`, ...). So a new feature never adds a field to an existing section: it adds a new section (with its own `serialize`, an entry in `KNOWN_SECTIONS`, optional on load). Otherwise a rollback to an older version, or an old server still running, deletes that data. A new section that depends on per-run state (for example the IPO count, or employee IDs) stores what it depends on and checks it against `ipo`/`team` on load, because older code keeps it frozen as it was. Publish rules and the rollback floor: docs/PUBLISH_RULES.md.
- **Wrap every DataStore call in `pcall`,** including `GetDataStore`.
- **Protect existing data:**
  - Never save over data that failed to load (the `data.loaded` check).
  - Keep the one-save-at-a-time lock.
- **Empty slots use `false`.** Arrays that are saved or sent over remotes use `false` for empty slots, because `nil` breaks arrays. Remember that `false ~= nil` when you check them.

## Secrets

- The Roblox API key lives in `.env` or `.env.txt`, and both are gitignored.
- Never print, log or commit the key. Never paste it into code, Studio or chat.
- Before every commit, check that `git status` doesn't list them.

## Studio and the repo

- The repo is the official copy of every `.lua` file. Team Create is the live place.
- **If you edit a `.lua` file,** the Studio script must match:
  - Push it through the Roblox Studio MCP if it's connected.
  - Otherwise, tell the user exactly which script to paste it into.

  Then playtest.
- **If you edit a script in Studio,** write the same source into its `.lua` file.
- Never push a script into Studio if someone else has claimed it.

## Testing

- Playtest in Studio (F5) and read the Output window.
- The game's creator automatically owns every game pass. To test as a normal player, use the shop's **Debug → "Ignore passes I really own"**.
- Check the phone layout with **Test → Device**.
- Egg timers run on real clock time. **Debug → Skip egg timers** speeds up tests.
