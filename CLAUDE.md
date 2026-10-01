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
- **Configs** are ModuleScripts in ReplicatedStorage:
  - `ShopConfig`: passes, products, `EggsEnabled`
  - `CreatureConfig`: creatures, rarities, eggs, odds, slots, poaching rules (`CreatureConfig.Poaching`)
  - `IpoConfig`: funding stages, IPO rewards (multiplier, Shares), cooldown, IPO shop perks
  - `OnboardingConfig`: the new-player free egg, goals, arrow and tracker settings
- **Clients** are LocalScripts in StarterPlayerScripts. They build their UI in code, only display server state, and send requests through the server-created remotes `ShopRemotes`, `EmployeeRemotes`, `PoachRemotes` and `IpoRemotes` in ReplicatedStorage.
- **UI conventions:**
  - One window open at a time, using the PlayerGui attribute `"OpenPanel"`.
  - HUD button slots: EGGS 0, SHOP 1, TEAM 2, POACH 3, IPO 4. They use the shared responsive layout: a column centered on the left, or a top row on short (phone) screens (height under 460).
  - Pop-up messages go at the bottom center.
  - Everything must work on a phone.
- **Studio-only debug tools** live in the shop's Debug tab. Add buttons with `ShopServer.addDebugAction`. They must stay behind `RunService:IsStudio()` and `ShopConfig.DebugInStudio`, so they never run on live servers.

## Server authority

- Game logic, prices, timers, random rolls, slots and income all run on the server.
- A client only asks, for example `TeamAction("BuyEgg", 2)`. The server checks everything: argument types, ranges, cash, ownership, and `data.ready`. It refuses anything invalid.
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
  onboarding = {                                 -- OnboardingServer.serialize (optional: older saves have none)
    seenIntro = boolean,                         -- the free egg was given (or wasn't needed): never given twice
    legacy = boolean,                            -- had a save before M5: counts as already onboarded
    arrowDone = boolean,                         -- the glowing arrow did its job (never comes back)
    goals = { goalKey, ... },                    -- finished goals (stay finished)
  },
}
```

- **Old saves must keep loading.** New fields are optional and get defaults. Bad or unknown values inside a section are skipped with a warning, never an error. Never rename or remove an existing field.
- **Never delete what you don't know.** `save()` writes back every top-level section of the loaded save that this version doesn't recognise (`KNOWN_SECTIONS` in TycoonCore), so older code never wipes a newer section. Eggs saved in incubators above the current count are kept the same way (EmployeeServer `parked`). Code that ran *before* this rule (anything older than milestone 4) can't do this: publish with **Shut down all servers** when a new section is added.
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
