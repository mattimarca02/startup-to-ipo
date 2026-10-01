# M4 re-review: save fixes F9, F2, F1

PR #6, branch `milestone-4-ipo`, code at `7387d56`. Review only, no game code changed. Checked by reading the code (no playtest, to keep the real DataStore save safe).

- **F9 `82d193f`: no partial save found.** `save()` refuses until `data.loaded` (`TycoonCore.lua:195`), which is set only after every `setupPlayer` returns inside `pcall` (`:443`), and it also refuses if any section is missing (`:196`). Leaving, autosave or `BindToClose` during load writes nothing. Leaving mid-setup returns at `:437`, and a setup error kicks without saving. After the 10 s pass timeout every section still exists. Passes aren't saved, so the save stays complete.
- **F2 `2f998a7`: no known section can be overwritten.** Only keys outside `KNOWN_SECTIONS` are kept (`:413-418`), and they are copied only into empty payload keys (`:220-224`). Parked eggs are cleared by an IPO both in memory (`EmployeeServer.lua:592`) and in the save (`TycoonCore.lua:261-265`).
- **F1 `3997046`: no HR reset left.** Both reset paths are gated by `IpoConfig.Resets.HRDepartment = false` (`TycoonCore.lua:266`, `:288`). The texts are built from that config. Old saves with no `ipo` get `count = 0`, which gives a multiplier of 1 (`IpoConfig.lua:147`); the capped legacy valuation never touches the multiplier.

## Findings

**Critical:** none. **High:** none. **Medium:** none.

**Low**
1. `TycoonCore.lua:453-456`, `ShopServer.lua:312-327`. If the pass check times out, loading goes on without the passes. Offline earnings are then paid without the 2x Cash or VIP multiplier, and an IPO done before Roblox answers misses the Shareholder x2. Both losses are permanent, but this only happens when Roblox is slow. **Fix:** flag the late pass check, pay the missing offline difference when it answers, and refuse `GoPublic` until it answers.
2. `TycoonCore.lua:409-411`. `saved.cash` and `saved.owned` aren't type-checked inside the new `pcall`. A bad value now kicks the player on every join (locked out) instead of warning. **Fix:** use `tonumber(saved.cash) or 0` and check `typeof(saved.owned) == "table"`.
3. `EmployeeServer.lua:527`, `PoachServer.lua:704`, `IpoServer.lua:355`. F2 only keeps unknown *top-level* sections. A new field inside an existing section (for example on employees or `ipo`) is still deleted by older code after a rollback. **Fix:** add a rule to CLAUDE.md that new saved data goes in a new top-level section, or have each `serialize` carry over the unknown keys of its section.
4. `TycoonCore.lua:220-224`. Kept sections are frozen as they were at join. An IPO, a poach or a hatch on the older server doesn't update them, so newer code can later read stale per-run data, or IDs of employees who have left. **Fix:** add a rule to CLAUDE.md that new sections re-check themselves against `team` and `ipo` on load (for example, store the `ipo.count` they belong to).
5. `TycoonCore.lua:205-237`. If a `serialize` or the IPO transform errors, `data.saving` stays true, and every later save (leaving, autosave, `BindToClose`, receipts) waits forever. No trigger exists today. **Fix:** build the payload inside the `pcall` and always clear `data.saving`.

**Counts:** Critical 0 · High 0 · Medium 0 · Low 5. **Verdict: merge.** The three fixes hold, and none of the Lows blocks the merge.
