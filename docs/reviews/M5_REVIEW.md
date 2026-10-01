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
| Studio Debug buttons | Registered only when `RunService:IsStudio()` (`OnboardingServer.lua:323-325`), and ShopServer's debug handler also refuses unless `IsStudio()` and `ShopConfig.DebugInStudio` (`ShopServer.lua:524`, and the remote itself only exists in Studio, `:593`). |

**No client input goes unvalidated.** The only value a client sends in M5 is the `action` string, and it's type-checked and matched exactly.

One weak spot (UX, not security):

- **F5 (Low):** `DismissTracker` is refused while `data.ready` is false, which includes the few seconds an IPO is being saved, and the reply says "Still loading" (`OnboardingServer.lua:195-197`). The client has already hidden the card and only `warn`s (`OnboardingClient.lua:337-347`), so the X isn't saved and the tracker comes back next session.

## 4. Interaction with M2, M3 and M4

| System | Result |
|---|---|
| Eggs with `EggsEnabled = false` (M2/M3) | Works. `EggsEnabled` is only read by `ShopConfig.lua:179` (which Robux items are for sale). The free Garage egg, the Cash egg shop and the Hatch prompt don't check it. "Hire 3" can be finished with Cash eggs. |
| Free egg and incubator perks | A new player has 3 base incubators and no FasterEggs perk, so the free egg always fits and runs the normal `hatchSeconds`. `grantEgg` uses the same `startEgg` as a bought egg. |
| IPO reset (M4) | **Kept, and that's correct.** The IPO save's transform leaves `payload.onboarding` alone (`TycoonCore.lua:257-273`) and `IpoConfig.Resets` has no onboarding entry. `seenIntro` stays true, so an IPO never gives a second egg. `arrowDone` and finished goals stay, so the arrow doesn't come back on the reset garage (`OnboardingServer.lua:173`). Even without the section, a post-IPO save has `ipo.count > 0`, so `hasProgress` would be true. |
| Seed goal after an IPO | Uses `stageValuation(index, ipo.count)` (`OnboardingServer.lua:135`), so the target grows with each IPO like the HUD does. Seed is always below the IPO-ready valuation, and the check runs every second while ready, so Seed is always marked before anyone can go public. |
| During an IPO save | `data.ready` is false, so the onboarding loop skips the player (`OnboardingServer.lua:340`). Nothing changes mid-IPO. |
| Poaching (M3): being poached | A brand-new player has the 15-minute new-player shield (`CreatureConfig.lua:126`), which covers the whole first minute. Exception: F3 (pre-M5 saves with no progress get no shield). Finished goals stay finished if an employee is taken later (`OnboardingServer.lua:150-155`). |
| Poaching (M3): poaching others | An employee taken from another player counts toward "Hire 3" (`OnboardingServer.lua:131` counts `team.employees`, and `addEmployee` puts them there). Not abusable (no reward), but see F6. |

- **F6 (Low):** the tracker can disappear before it's finished. It only shows once `#employees >= TrackerAfterEmployees` or the arrow is done or a goal is finished (`OnboardingServer.lua:183-185`). A player who loses their only employee before any of that (fires it, or F3's unshielded case) loses the tracker until they hire again. Also, "Hire 3 employees" is completed by poaching, which the text doesn't suggest. Fix: save a `trackerShown` flag once it first appears, and use it in place of the employee count.

## 5. Client robustness and phone layout

| Check | Result |
|---|---|
| `pcall` around DataStore calls | M5 adds no DataStore call. The only client request, `InvokeServer("DismissTracker")`, is in a `pcall` (`OnboardingClient.lua:341-343`). |
| Nil checks | Attributes are type-checked before use (`OnboardingClient.lua:135`, `:312`, `:315`). `WaitForChild` on the character has a timeout (`:120`). The server loop runs each player in a `pcall` (`OnboardingServer.lua:341-344`). |
| Arrow loop | One `RenderStepped` connection for the whole session, and it returns at once when the marker is hidden (`OnboardingClient.lua:146-153`). No leak. |
| Arrow per respawn | A new `Attachment` goes into each new `HumanoidRootPart` (`:119-127`) and is destroyed with the old character. No leak. |
| Toast loop | One `task.delay` per toast, using a token so only the newest one hides it (`:188-199`). No leak. |
| Toast position | `-184` from the bottom, above the poach (`-128`), egg (`-72`) and shop/IPO (`-16`) toasts. Bottom center, as CLAUDE.md asks. |
| Tracker and open windows | Hidden while `OpenPanel` is set (`:334`), except for F10. |

**F1 (Medium): the goal card never finds the valuation bar, so it's misplaced or cut off on some phones.**

- **Where:** `OnboardingClient.lua:287-288` waits for `IpoWindowGui.ValuationBar`, but the bar's parent is `IpoGui` (`IpoClient.lua:177-185`, `Parent = gui`; `IpoWindowGui` is `front`). After 30 seconds `WaitForChild` returns nil without a warning, and the card always uses the fixed fallback spots (`OnboardingClient.lua:278-282`). The phone pass didn't catch it because on a normal desktop screen the fallback `(98, 84)` happens to sit right under the bar.
- **What breaks:**
  - **Narrow portrait phones (under ~358 px wide, e.g. 320 px):** IpoClient shrinks the bar to fit (`IpoClient.lua:244`), but the card stays 250 px wide at x = 98. Its right edge, including the X button, is off-screen, so the player can't close it.
  - **Short and narrow landscape screens (height under 460, width under 560):** the bar moves to `(10, 76)` (`IpoClient.lua:235`), the same spot as the card's fallback, so the card covers the valuation bar.
- **Fix:** `playerGui:WaitForChild("IpoGui", 30)` in place of `"IpoWindowGui"`. Then test at 320 × 568 and a small landscape device in **Test → Device**.

**F2 (Low): on landscape phones the card overlaps the poaching panels.** On short screens the Negotiation and Poach Alert panels sit at y = 76, centered, up to 460 px wide and 92 px tall (`PoachClient.lua:807-816`, `:878-880`). The card is at y = 76 too (fallback `(10, 76)`, or `(370, 76)` once F1 is fixed). On an 844 × 390 phone they overlap by about 70 px; on a 667 × 375 phone by about 150 px. New players are shielded from poach alerts, but a new player who poaches someone sees the Negotiation panel. **Fix:** hide the card while either poach panel is visible, or move it below them.

**F7 (Low): the free-egg toast is sent during the load, often before the screen is up.** `notify` fires from inside `setupPlayer` (`OnboardingServer.lua:88`, called from `TycoonCore.lua:453`). Roblox holds the event until `OnboardingClient` connects (`:200`), but the toast then shows for 3.5 s, which may still be during the loading screen or before the camera is on the plot. **Fix:** send it on the first update loop after `data.ready`, or when the client first asks for state.

**F10 (Low): the "All goals done!" card ignores open windows for 3 s.** While `celebrating`, `refreshTracker` returns before the `OpenPanel` check (`OnboardingClient.lua:333-334`), so the card stays on top of a window opened in those 3 seconds. **Fix:** apply `card.Visible = playerGui:GetAttribute("OpenPanel") == nil` during the celebration too.

## 6. Ranked findings

| # | Level | Where | What breaks | Fix |
|---|---|---|---|---|
| F1 | **Medium** | `OnboardingClient.lua:287-288` | Looks for `ValuationBar` in `IpoWindowGui`, but it's in `IpoGui`. The card never follows the bar: on portrait phones under ~358 px its X button is off-screen, and on short narrow landscape screens it covers the valuation bar. | `WaitForChild("IpoGui", 30)`; retest in Test → Device at 320 × 568 and a small landscape size. |
| F2 | Low | `OnboardingClient.lua:278-282`, `PoachClient.lua:807-816`, `:878-880` | On landscape phones the card overlaps the Negotiation / Poach Alert panels (both at y = 76). | Hide the card while a poach panel shows, or place it below them. |
| F3 | Low | `OnboardingServer.lua:248-255`, `TycoonCore.lua:452`, `PoachServer.lua:694-695` | Pre-M5 saves with no progress get the tutorial but not the 15-minute new-player poach shield, so their first employee can be taken. | Give the new-player shield whenever the free egg is given (e.g. a small `PoachServer.grantNewPlayerShield(player)` called from `grantFreeEgg`; PoachServer must be claimed first). |
| F4 | Low | `OnboardingServer.lua:169`, `:248`, `:253` | Sessions with `Enabled = false` save `seenIntro = false, legacy = false`; turning it back on shows the arrow and tracker to veterans. | In `setupPlayer`, treat any `not seenIntro and hasProgress(data)` as legacy, whether or not the section exists. |
| F5 | Low | `OnboardingServer.lua:195-197`, `OnboardingClient.lua:337-347` | Closing the tracker during an IPO save (or while loading) isn't saved; it comes back next session, with a "Still loading" reason. | Retry the dismiss until the server accepts it; say "Your IPO is being filed" when that's the reason. |
| F6 | Low | `OnboardingServer.lua:131`, `:183-185` | The tracker disappears if the player loses their only employee before a goal is finished. Poached employees count toward "Hire 3". | Save a `trackerShown` flag the first time it appears and use it in `started`. |
| F7 | Low | `OnboardingServer.lua:88`, `TycoonCore.lua:453` | The free-egg toast is sent during the load and may be shown behind the loading screen. | Send it from the first update after `data.ready`. |
| F8 | Low | `TycoonCore.lua:423` (no session lock) | Hopping servers before the first save lands can give the egg again in the new server; the player ends with one egg but loses the first session's seconds of progress. Older than M5. | Session lock in M9, as planned. |
| F9 | Low | `OnboardingServer.lua:222-227` | Bad values in the section are coerced silently, without the warning CLAUDE.md asks for. Safe (`hasProgress` still guards the egg). | `warn` when a field is present but isn't a boolean, or `goals` isn't a table. |
| F10 | Low | `OnboardingClient.lua:333-334` | The "All goals done!" card stays over a window opened during its 3 s. | Respect `OpenPanel` while celebrating. |

**Counts:** Critical 0 · High 0 · Medium 1 · Low 9.

## 7. Verdict

**Merge.** Nothing blocks it.

- Save integrity holds: the onboarding section is inside the M4 F9 gate, survives M4 code and IPOs, and old saves load correctly.
- The free egg can't be duplicated: the egg and `seenIntro` always land in the same save, and no remote can reach `grantEgg`.
- No client input grants anything.
- **Fix F1 before publishing.** It's a one-word change in `OnboardingClient.lua` (already claimed by this branch), and "everything must work on a phone" is a project rule.
- Publish with **Shut down all servers**, because M5 adds a new save section (CLAUDE.md, M4 F2).
- The Lows can go to the ROADMAP backlog, like the M4 re-review's.
