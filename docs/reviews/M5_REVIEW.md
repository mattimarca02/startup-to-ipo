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
