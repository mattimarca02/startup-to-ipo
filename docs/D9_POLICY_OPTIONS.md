# D9: what players in restricted regions see (Paid Random Items)

Decision for Mattia. Nothing here is built yet. Source: review finding FR-13 in docs/reviews/FULL_REVIEW.md, Roblox's [Paid Random Items guidelines](https://create.roblox.com/docs/production/monetization/paid-random-items) and the [2026-05-26 clarification](https://devforum.roblox.com/t/clarifying-requirements-for-paid-random-items/4654622).

## The rule

> "Creators offering Paid Random Items must use the `ArePaidRandomItemsRestricted` attribute of PolicyService:GetPolicyInfoForPlayerAsync to ensure these items are only accessible to eligible users."

The restricted regions named are **Australia, Belgium, the Netherlands, the United Kingdom and Brazil**. For those players the guidelines accept one of these treatments: an unpaid, earnable path; a predetermined (non-random) sequence; a direct, guaranteed purchase; removing or hiding the item; blocking it with a message; or keeping the player out of that part of the game.

## Why our eggs count, and what the Cash packs have to do with it

- A Paid Random Item is "purchased directly with Robux, or indirectly via in-game currencies purchased with Robux, that yield a random outcome".
- Eggs give a random creature (`EmployeeServer.rollCreature`) and are bought with **Cash**.
- **Cash is sold for Robux:** Pile, Bag and Vault of Cash (`ShopConfig.Products`, keys `CashSmall`, `CashMedium`, `CashLarge`). They are not marked `needsEggs`, so they are **on sale today**, whatever `EggsEnabled` says. Cash is one pool: a player can't tell bought Cash from earned Cash, so every egg bought with Cash counts as a paid random item while Cash packs are sold.
- **Luck Boost** (Robux) changes the odds: the guidelines list luck boosts as paid random items too.
- Less clear: the **2x Cash** and **VIP** passes multiply Cash earned, and the **Shareholder** pass doubles the Shares that buy the Talent Scouts luck perk. They don't sell currency directly. The options below say where this matters.
- Not affected: the free eggs from onboarding and the daily calendar (not paid), Instant Hatch (it skips a timer; the outcome is already decided by the same roll), Poach Shield, the HR Department.

## Part every option shares (S)

In `ShopServer.setupPlayer`, next to the pass check and with the same 10 s cap: `pcall(PolicyService.GetPolicyInfoForPlayerAsync, PolicyService, player)`, read `ArePaidRandomItemsRestricted`, store `shop.randomRestricted`, publish it as a player attribute for the screens. **If the call fails, treat the player as restricted** (fail closed: the policy puts the burden on us). It is not saved: it is checked on every join, because a player's region can change.

## The options

| | A. No paid route to Cash or luck | B. Fixed hire order (recommended) | C. No egg purchases | D. Eggs cost an earn-only currency, for everyone | E. Do nothing |
|---|---|---|---|---|---|
| **What changes in the code** | ShopClient (and PoachClient for the shield card, unchanged) hides Cash packs and Luck Boost when the attribute is set; the purchase buttons say "Not available in your region". ShopServer refuses to *prompt* them server-side (the VIP door only prompts a pass, unaffected). | `EmployeeServer.rollCreature`: for restricted players, no random roll: the next creature comes from a fixed per-egg order that follows the odds (e.g. a 100-step list per egg). A counter per egg in a **new top-level save section** `fixedHires` (rule A10). EmployeeClient shows "Next hire from this egg: Coding Cat" instead of the odds. Luck Boost hidden for them (it would do nothing). | `EmployeeServer.buyEgg` refuses for restricted players; the Eggs tab says why. Free eggs (onboarding, daily) still hatch. | New currency (e.g. "Recruiting Tokens") earned by playing, never sold; eggs priced in it; new save section; economy retune and `economy_sim.py` rerun. Luck Boost still needs gating (A or B for it). | Only the shared part, or nothing. |
| **What changes for players there** | No Cash packs or Luck Boost. Eggs work as now with earned Cash. | Eggs work as now, but they know what they'll get; no luck items. Everything else on sale. | The core loop (buy eggs, hatch, build a team) is gone; only free eggs. | Same for every player worldwide: eggs cost tokens. | Nothing. |
| **Effort** | **S** | **M** (server roll, one save section, one screen, tests) | **S** | **L** | none |
| **Revenue impact** | Loses Cash pack and Luck Boost sales in those regions (Cash packs are likely the main repeat purchase). | Loses only Luck Boost sales there. Cash packs, passes, Instant Hatch, Poach Shield keep selling. | Loses most engagement and spending there (players quit). | Cash packs lose their main use for everyone; big global revenue risk until retuned. | None until moderation. |
| **Moderation risk if skipped / left open** | Medium: the 2x Cash and VIP passes still feed the Cash that buys random eggs; Roblox may count that. Also, a client can't be stopped from calling `PromptProductPurchase` itself, so a hidden Cash pack is still *buyable* by an exploiter in those regions. | Low: there is no random outcome left for those players to pay for, and the server enforces it (no client involved). | Low. | Low for eggs; Luck Boost still needs a treatment. | **High.** The clarification names these regions and requires the PolicyService check; moderation can restrict monetization or the game. |

**Size of the regions (estimate, to check after launch):** together the five are roughly a tenth of Roblox's players, and the UK and Australia spend more per player than average. Roblox's Analytics (Audience > Country) will give the real share in the first week.

## Recommendation

**B, plus the shared PolicyService check.** It is the only option that is enforced entirely on the server (the roll), it doesn't depend on how Roblox reads the Cash multiplier passes, it keeps almost all revenue in those markets, and failing closed (treating a player as restricted when the check errors) only gives a normal player one session of fixed-order eggs.

If launch can't wait for B (M effort), ship **A** as a stop-gap only after asking Roblox (Creator Support or the DevForum thread) whether a Cash multiplier pass makes earned Cash "purchased with Robux". If the answer is yes, A isn't enough and B is required.

Either way, answer "Yes, paid random items" in the experience questionnaire (checklist C9), and keep the per-hire odds from FR-12 visible to everyone else.

## When a player's restriction changes between sessions (decided while building B)

A player can be restricted in one session and not in the next, or the reverse: they travel, Roblox changes the region list, or the check failed once (fail closed). What happens:

1. **Decided once per session.** The check runs on join (next to the pass check, same 10 s cap) and the answer holds until they leave. Never saved, never changed mid-game (only the Studio Debug toggle "Paid random items: restricted on/off" switches it, for tests).
2. **The counter keeps going, it never restarts.** Each egg's counter in `fixedHires` moves only when a restricted player hatches that egg. In an unrestricted session it stays as it was and is saved unchanged. Back in a restricted session the order continues where it stopped, so nobody gets the start of an order twice. An IPO doesn't touch it, and older code keeps the section unchanged (rule A10).
3. **No egg is lost, refunded or doubled.** Eggs in incubators stay. The creature is decided when the egg hatches, by the session it hatches in: restricted, the egg's next fixed hire; not restricted, a random roll with the odds on screen. The fixed order follows the same odds, so neither side is worth more. An egg bought while "Next hire: X" was shown that hatches in an unrestricted session rolls randomly; X stays next in the order for a later restricted session.
4. **Luck Boost is never wasted.** While restricted it is put aside and doesn't count down (it would do nothing: there is no roll). It runs again in an unrestricted session. A Luck Boost bought anyway while restricted (a client can open Roblox's prompt by itself) goes into that kept time.
5. **Nothing else changes:** Instant Hatch tokens, passes, a hire waiting for a desk, the daily streak. Talent Scouts counts on both sides: it changes the fixed order the same way it changes the odds.
6. **No way to game it:** switching can't reset the counter, and a random hatch never moves it, so an unwanted next hire stays next until a restricted hatch takes it.
7. **A failed check** gives a normal player one session of fixed-order hires (same odds) with Luck Boost put aside. Nothing is lost; the next join asks again.
