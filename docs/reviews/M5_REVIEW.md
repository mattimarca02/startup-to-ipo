# M5 review: first minute (onboarding)

Branch `milestone-5-onboarding`. Code reviewed at commit `a54434b` (diff `main...a54434b`). All `file:line` references point at that commit. Review only: no game code, Studio or Roblox was changed.

Finding numbers here (F1, F2, ...) are this review's own. "M4 F9" and "M4 F2" mean the findings in `docs/reviews/M4_REVIEW.md`.

## Severity scale

| Level | Meaning |
|---|---|
| Critical | A client can cheat, or player data or Robux value is lost or duplicated in a normal situation. Blocks the merge. |
| High | A bug that normal players will hit. Should block the merge. |
| Medium | A real bug in an uncommon situation, or the code does something different from what ROADMAP promises. Fix before launch. |
| Low | A rare edge case, a confusing message, or a safety net that's missing. Fix when convenient. |

## 1. Save integrity

**Result: no partial save is possible.** The new section is held to the same rules as the others.

| Question | Answer |
|---|---|
| Is OnboardingServer inside the M4 F9 load gate? | Yes. `OnboardingServer.setupPlayer` runs last inside the setup `pcall` (`TycoonCore.lua:453`), and `data.loaded` is set only afterwards (`TycoonCore.lua:461`). |
| Can a save be written during load? | No. `save()` refuses until `data.loaded` (`TycoonCore.lua:197`) and also refuses if `data.onboarding` is missing (`TycoonCore.lua:198`). Autosave, leaving and `BindToClose` all go through `save()`. |
| After a slow load (pass check waits up to 10 s)? | Same gate. If the player left while loading, `playerData[player] ~= data` returns before anything is set (`TycoonCore.lua:455`), and PlayerRemoving's `save()` already found no loaded data. |
| If onboarding setup errors? | `data.onboarding` is set at `OnboardingServer.lua:242`, before the free egg. An error after that fails the `pcall`, kicks the player and never sets `data.loaded` (`TycoonCore.lua:456-460`). Nothing is saved, the DataStore copy stays as it was. |
| Does onboarding setup yield? | No. `grantEgg` → `startEgg` → `push` and `notify` are `FireClient` calls, which don't yield. No new DataStore calls were added. |
| `BindToClose` | Unchanged (`TycoonCore.lua:527-531`). Each save carries the onboarding section because of the gate above. |
| Old saves with no `onboarding` section | Handled at `OnboardingServer.lua:248-252`: a save with progress becomes `legacy = true, seenIntro = true` (no egg, arrow or tracker). A save with no progress is treated as new. |
| Old code (M4, after the M4 F2 fix) | `onboarding` is unknown to M4's `KNOWN_SECTIONS`, so M4 writes it back unchanged. M5's own `serialize` keeps unknown *fields* inside the section (`OnboardingServer.lua:234-238`, `:274-278`). |
| Code from before the M4 F2 fix | Would drop the section. The player then has progress (the egg, or what hatched from it), so M5 marks them `legacy` and doesn't give a second egg; they just lose the arrow and tracker. ROADMAP already requires **Shut down all servers** for M4's publish, so this code shouldn't be running anywhere. Do the same for M5's publish (new section). |
| IPO save | `commitIpo`'s transform (`TycoonCore.lua:257-273`) doesn't touch `payload.onboarding`, so the IPO save keeps it. See section 4. |

Minor: bad values inside the section are coerced silently (`seenIntro = "yes"` becomes `false`) with no warning (`OnboardingServer.lua:222-227`), while CLAUDE.md asks for a warning. It's safe, because `hasProgress` still guards the free egg. Recorded as **F9** (Low).

## 2. Duplicate or lost free egg

**Result: no way to get a second free egg in normal play.** The egg and `seenIntro = true` are always written by the same save, because they live in the same payload (`OnboardingServer.lua:76-90`). They can't be saved apart.

| Scenario | What happens |
|---|---|
| Double join (two `PlayerAdded` for one player) | Roblox doesn't fire that. A second session of the same account kicks the first; see "two servers". |
| Leaves in the first seconds, while loading | Nothing is saved (section 1). Next join they're still new and get the egg then. Nothing lost, nothing doubled. |
| Leaves in the first seconds, after loading | The leave save holds the egg and `seenIntro = true` together. Next join: section present, no new egg. |
| That leave save fails | Neither the egg nor `seenIntro` is stored. Next join gives the egg once. Correct. |
| Rejoin mid-tutorial | `arrowDone`, `dismissed` and finished `goals` are saved and come back. The egg keeps its real-clock timer. Works. |
| Save fails to load | `loadOk = false` → `legacy = true`, no egg (`OnboardingServer.lua:244-247`), and the session never saves. Correct. |
| Two servers at once | There's no session lock (known, planned for M9). If the player hops to server B before server A's first save lands, B reads "no save" and gives the egg again. A's save then lands and B's later saves overwrite it, so the player ends with **one** egg and loses A's few seconds of progress. That's the old no-lock problem, not a duplicate. Recorded as **F8** (Low). |
| An IPO | The section is kept (section 4), so `seenIntro` stays true. |
| A Robux purchase in the first minute | `ProcessReceipt` saves right away, and that save already has `seenIntro = true`. |

**Is `hasProgress` airtight?** It's only asked when the save has *no* onboarding section (`OnboardingServer.lua:248`, `:253`), so after the first M5 save it no longer matters. It checks Cash, upgrades, employees, pending hire, every incubator, parked eggs, IPO count/Shares/lifetime/perks, receipts, Instant Hatch tokens and HR/poach notes (`OnboardingServer.lua:41-52`). The shapes match the real data: `shop.receipts` is an array (`ShopServer.lua:281`), `poach.lost`/`gained` are maps (`PoachServer.lua:658-659`), and PoachServer's offline `refund` is already added to Cash before onboarding runs (`PoachServer.lua:688-691`).

One theoretical hole: a player who hatches the free egg and **fires** that employee within the same second has no trace left (Cash 0, no employee, lifetime 0). That only matters if the onboarding section is then also lost, which needs code from before M4 F2 to save over it. Not reachable today; no fix needed beyond publishing with **Shut down all servers**.

Two smaller gaps were found:

- **F3 (Low):** "new player" means two different things. Onboarding treats a pre-M5 save with no progress as new and gives the free egg (`OnboardingServer.lua:248-255`), but PoachServer's 15-minute new-player shield only goes to `saved == nil` (`TycoonCore.lua:452`, `PoachServer.lua:694-695`). Players who joined before M5 and left without buying anything (likely a large share of past visitors) get the tutorial but can be poached as soon as their first employee hatches.
- **F4 (Low):** `OnboardingConfig.Enabled = false` still saves a section with `seenIntro = false, legacy = false`. If it's switched back on, those players skip the egg (they have progress) but are not `legacy`, so the arrow and tracker show up for veterans (`OnboardingServer.lua:169`, `:248`, `:253`).

## 3. Server authority

**Result: no remote can grant anything.** M5 adds one RemoteFunction and one RemoteEvent, both in `OnboardingRemotes` (`OnboardingServer.lua:312-321`).

| Remote / path | Checked |
|---|---|
| `OnboardingAction` (RemoteFunction) | Only `"DismissTracker"` is accepted. `action` must be a string (`OnboardingServer.lua:193`), data must be ready (`:195`), anything else is "Unknown action" (`:203`). Extra arguments are ignored. Dismissing only sets `dismissed = true` and hides the tracker; it gives nothing and can't un-finish or finish a goal. Spamming it is harmless (no yield, no save). |
| `OnboardingNotify` (RemoteEvent, server → client) | The server only fires it (`OnboardingServer.lua:70-74`) and never listens. A client calling `FireServer` on it reaches no code: Roblox queues the calls up to a fixed limit, then drops them with a warning in the server log. Same as the existing `TeamUpdate` and `EggHatched`. Not a finding. |
| The free egg | `EmployeeServer.grantEgg` (`EmployeeServer.lua:316-325`) is a module function, not a remote action: it isn't in `ACTIONS` (`EmployeeServer.lua:419-427`). Only `OnboardingServer.setupPlayer` and the Studio Debug restart call it. |
| `buyEgg` refactor | Behaviour is unchanged: same validation, free incubator check, Cash check before the deduction, then the shared `startEgg` (`EmployeeServer.lua:301-312`). |
| Goals | Computed every second from server data only (`OnboardingServer.lua:129-163`). There's no remote that reports progress, and finishing a goal grants nothing. |
| Arrow target | Picked by the server (`OnboardingServer.lua:96-114`) and sent as an attribute. The client only draws it. |
| Hatching the free egg | Uses the normal `ProximityPrompt` → `hatch()` path, which checks the owner, `data.ready` and the timer (`EmployeeServer.lua:486-490`, `:246-251`). No onboarding exception. |
| Studio Debug buttons | Registered only when `RunService:IsStudio()` (`OnboardingServer.lua:323-325`), and ShopServer's debug handler also refuses unless `IsStudio()` and `ShopConfig.DebugInStudio` (`ShopServer.lua:525`). |

**No client input goes unvalidated.** The only value a client sends in M5 is the `action` string, and it's type-checked and matched exactly.

One weak spot (UX, not security):

- **F5 (Low):** `DismissTracker` is refused while `data.ready` is false, which includes the few seconds an IPO is being saved, and the reply says "Still loading" (`OnboardingServer.lua:195-197`). The client has already hidden the card and only `warn`s (`OnboardingClient.lua:337-347`), so the X isn't saved and the tracker comes back next session.
