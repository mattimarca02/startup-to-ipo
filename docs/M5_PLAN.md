# M5 plan: first minute (onboarding)

Planning only. No game code, no Studio, no Roblox changes in this doc or this branch yet.
Goal from ROADMAP.md: *"a new player earns, hatches and buys within 60 seconds without reading anything."*

## 1. The first 60 seconds

A brand-new player (no save, or `saved.onboarding` missing/`seenIntro == false`) spawns into their garage like today, but with two things already true the moment they land:

- **A Garage Egg is already incubating** in incubator 1 — granted free, server-side, in `PlayerAdded`, before the player can do anything. They don't need to find the EGGS panel or spend Cash first.
- **A glowing arrow/beam** (a simple client-side `BillboardGui`/beam, no new remote) points from the spawn point to incubator 1, replacing the need for text instructions.

Timeline, matching `docs/ECONOMY.md`'s own numbers so we don't re-promise something the economy can't deliver:

| Time | What happens | System used |
|---|---|---|
| t=0s | Spawn in garage. Free Garage Egg already incubating (hatch = 60s, same timer as `CreatureConfig.Eggs.Garage.hatchSeconds`). Arrow points at the incubator. | Existing incubator, no new timer value |
| t=0-60s | Player is free to walk to the green pad and buy the Desk-chain upgrades (free Desk, then Coffee Machine at 25 Cash — they'll have earned that from the Desk's 1/s income alone by t=25s). Arrow stays on the incubator until the egg is hatched. | Existing `UPGRADES` pad |
| t=60s | Garage Egg is ready. **This one egg only** auto-hatches for every new player, independent of the Auto-Hatch pass (see open question 1) — or the arrow switches to point at the "Hatch" `ProximityPrompt` and waits for a touch. Either way the first employee joins by minute 1. | `EmployeeServer.hatch`, existing reveal flow |
| t=60s+ | First employee walks the garage (existing `placeEmployees`), income ticks up. Goal tracker appears: "Hire 3 employees" and "Reach Seed stage" (see section 2). | Existing `EmployeeServer` team, `IpoServer` stage attributes |

This reuses `docs/ECONOMY.md`'s own finding: the real bottleneck isn't Cash, it's the hatch timer. Giving the first egg for free (skipping the 250-Cash cost, not skipping the 60s timer) is the only new behavior — everything else (pad, income, hatch, reveal) is the existing build. First IPO still lands at ~12 minutes of active play per the econ sim; this plan doesn't touch that number, it only removes the ~5-minute delay before a player finds the egg system at all (finding 1 in ECONOMY.md: "the first employee arrives at minute 5, not minute 1").

## 2. Tutorial/goal-tracker flow (existing systems only)

No new currencies, no new pads, no new remotes beyond what's needed to read existing state. A small HUD card (bottom area, not a 6th button — see section 5) shows 1-2 live goals pulled from state the client already receives:

1. **"Hire 3 employees"** — reads `team.employees` count from the existing `EmployeeServer` snapshot (`EggHatched`/update remote already pushes this).
2. **"Reach Seed stage"** — reads the `IpoValuation`/stage attributes `IpoServer` already sets (`player:SetAttribute("IpoValuation", ...)`), compared against `IpoConfig.Stages[2]` (Seed, valuation 1800).

Both goals disappear (or get crossed off) once true; the whole tracker hides once both are done or a time/IPO cap is hit (open question 2). No goal unlocks a reward by itself — reaching Seed/hiring 3 already matters in the existing economy (stage display, team income). The tracker is pure UI sugar over state that already exists; it does not grant anything.

Flow order a new player naturally follows, using only shipped systems: spawn → free egg hatches (eggs) → buy upgrades with pad income (shop pad, not the Shop window) → hire more via bought eggs (eggs) → reach Seed (IPO stage display) → eventually Go Public (IPO). Poaching and the Shop window are deliberately not pushed in the first minute — they're other players' systems and a monetization surface, not onboarding goals.

## 3. Save: what must persist (fits F2's unknown-section rule)

New top-level save section, same pattern as `poach`/`ipo` (both "optional: older saves have none"):

```lua
onboarding = {         -- OnboardingServer.serialize (optional: older/other saves have none)
  seenIntro = boolean,  -- true once the free egg has been granted (never granted twice)
  goalsShownAt = os.time() or nil,  -- when the goal tracker first appeared, for the 10-minute window
}
```

- Added to `TycoonCore`'s `KNOWN_SECTIONS` table alongside the existing six keys, exactly like `poach`/`ipo` were added for M3/M4.
- A save with no `onboarding` key (every existing save today) defaults to `seenIntro = false` — on next login the player gets the free-egg flow once, then it's marked seen and never repeats. This matches the "new fields are optional and get defaults" rule in CLAUDE.md's Save format section.
- Follows the standard module contract: `OnboardingServer.init(core)`, `OnboardingServer.setupPlayer(player, data, savedOnboarding)`, `OnboardingServer.serialize(data)` — same shape as `ShopServer`/`EmployeeServer`/`PoachServer`/`IpoServer`. No second DataStore, no second save loop.
- `seenIntro` is set to `true` by the **server**, at the moment it grants the free egg (not when the client claims to have seen the arrow) — see section 4.

## 4. Server authority

Nothing the client reports grants a reward — same rule as purchases:

- The free Garage Egg is placed into `team.incubators[1]` by server code in `PlayerAdded` (inside `OnboardingServer.setupPlayer`, called from `TycoonCore` after `EmployeeServer.setupPlayer`, the same spot `IpoServer`/`PoachServer` already hook in). The client never asks for it and can't ask twice — `seenIntro` is checked and flipped server-side in that same call, before any client script runs.
- The 60s hatch timer and the auto-hatch-this-one-egg behavior (if we go that route — open question 1) follow the existing `hatch()`/incubator-ready path in `EmployeeServer`; the client only touches a `ProximityPrompt` that triggers a server-validated `Hatch` action, exactly like every other egg today. No new trust boundary.
- The goal tracker is **read-only on the client**: it displays `team.employees` count and `IpoValuation`/stage attributes the server already pushes/sets. The client never tells the server "I hired 3" or "I reached Seed" — there is no such remote. If we ever want a reward for finishing the tracker (not in this plan — see section 2, goals don't grant anything), it would have to be the server noticing the same state change it already owns, never a client claim.
- `OnboardingClient.lua` sends no new remote calls that affect `playerData` — at most it might ask `EmployeeServer`'s existing `Sync` action to refresh state after the panel opens, which already exists and is already server-validated.

## 5. Phone layout and safety

- **No sixth HUD button.** `CLAUDE.md`'s HUD convention is EGGS 0 / SHOP 1 / TEAM 2 / POACH 3 / IPO 4, with the responsive column/top-row split at 460px height. The goal tracker is a small dismissible card using the existing bottom-center pop-up convention (same area as `showToast` in `EmployeeClient.lua`), not a new panel and not a new `OpenPanel` state, so it can't block or compete with any existing window on a phone screen.
- **The arrow/beam** must be visible and not obstruct touch controls — reuse the existing `BillboardGui`/`ProximityPrompt` approach already used for incubators and the IPO pad, scaled the same way, tested at the same screen sizes other panels are (`Test → Device`, per CLAUDE.md Testing section).
- **No free-text input anywhere in onboarding.** The flow is 100% server-driven state + taps/touches (walk to egg, touch pad, touch hatch prompt) — it never asks the player to type anything, so it adds no new surface to the chat/age-safety picture. `ChatTags.lua` and chat itself are untouched by this milestone.
- Per ROADMAP's "Launch requirements" section, new Roblox games first reach only age-checked 16+ players; under-16 access unlocks later after 250 "highly engaged" plays. M5 doesn't change that gate or interact with chat, so there's nothing in this milestone that needs separate under-16 handling — it's a pure solo-garage flow for the player's own screen.

## 6. Files to add or change

| File | Change |
|---|---|
| `OnboardingServer.lua` (new) | ModuleScript, ServerScriptService. `init(core)` / `setupPlayer(player, data, savedOnboarding)` / `serialize(data)`, same contract as the other feature modules. Grants the free Garage Egg once, owns `seenIntro`/`goalsShownAt`. |
| `OnboardingClient.lua` (new) | LocalScript, StarterPlayerScripts. Draws the arrow/beam to the first incubator and the bottom-center goal-tracker card. Pure display, reads existing remotes/attributes only. |
| `TycoonCore.lua` | Add `onboarding = true` to `KNOWN_SECTIONS`; `require` and `init` `OnboardingServer` (after `EmployeeServer`, since it needs a free incubator slot to exist); include its `serialize()` in `save()`'s payload, same pattern as the other four modules. |
| `EmployeeServer.lua` | Export one small function (e.g. `EmployeeServer.grantFreeEgg(player, eggKey)`) so `OnboardingServer` can place an egg into incubator 1 without going through `buyEgg`'s Cash check — reuses the same incubator-state shape `buyEgg` already writes. |
| `README.md` | Add `OnboardingServer.lua`/`OnboardingClient.lua` rows to the file-structure table. |
| `CONTRIBUTING.md` | Add both new files to the Ownership table, claimed by whoever builds M5. |
| `ROADMAP.md` | Status update at the end of the milestone (not now — per CLAUDE.md, that happens when M5 is actually built and done). |

## 7. Build order (3-5 small commits, for the future build branch)

1. `OnboardingServer` skeleton wired into `TycoonCore`: new save section, `KNOWN_SECTIONS` entry, free-egg grant on first join (server-side only, no UI). Playtest by reading server Output — confirm the egg appears in incubator 1 and `seenIntro` is saved true.
2. `OnboardingClient`: the glowing arrow from spawn to incubator 1, nothing else yet.
3. Goal-tracker card (Hire 3 / Reach Seed), reading existing team/IPO state, bottom-center per the toast convention.
4. Auto-hatch-or-prompt decision for the free egg at t=60s (pending open question 1), plus hiding the tracker once both goals are done or the time/IPO cap is hit (open question 2).
5. Studio Debug tab button (`ShopServer.addDebugAction`, `IsStudio()`-gated like all debug tools) to reset `onboarding.seenIntro` for repeat testing, and a phone-layout pass (`Test → Device`).

## 8. Open questions

1. Should the free Garage Egg auto-hatch for every new player at t=60s regardless of the Auto-Hatch pass (a one-time onboarding exception), or should the player have to walk up and tap the hatch prompt themselves?
2. Should the goal tracker hide itself after a fixed window (e.g. 10 minutes) even if "Reach Seed" isn't done yet, or stay until both goals are complete?
3. Is a brand-new `OnboardingServer.lua` module the right shape, or would you rather fold this smaller amount of state into `EmployeeServer` (it already owns incubators) instead of a fifth feature module?
4. Any reward at all for finishing both goals (even a cosmetic toast, no Cash/Shares), or is the tracker purely informational with no completion payoff?
5. Should returning players who had an old save from before M5 (so `onboarding` is missing) get the free egg too, or only players with genuinely no save at all?
