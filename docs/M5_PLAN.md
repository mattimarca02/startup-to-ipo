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
