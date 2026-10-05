# Customize PR 1: notes, questions and deviations

PR 1 of docs/CUSTOMIZE_PROPOSAL.md section 6 (branch `customize-pr1`): the `pokedex` save section (the whole format), `CompanyServer`, `CompanyConfig`, `SectorConfig`, and the `"Place"` / `"Store"` / `"Sync"` requests. Invisible to players. Where the doc was silent, ambiguous or in conflict with the code, I chose the **safest reading** and wrote it here. Each item says what the doc says, what I did and why, and the question for the owner.

## Questions (the owner decides; each has a safe default in the code)

1. **An IPO done by PR 1's own code.** *Resolved by the owner, applied in the review fix (`customize-pr1-fix`).* The first version of PR 1 left `run` behind after an IPO (the IPO transform is PR 4), so the next join took it for an IPO an older version ran and wrote a Bronze stamp and a card. **Owner decision (default confirmed): for IPOs done before PR 4, `pokedex.run` simply follows the IPO count: no stamp, no card, no sector completion until PR 4 turns stamps on.** In code: `commitIpo` calls `CompanyServer.writeIpoRun` inside the IPO's save transform (the payload that is written carries `run = the new count`, so a crash right after the save leaves nothing behind) and `CompanyServer.onIpo` after the save worked (the section in memory follows, so the next autosave and a second IPO in the same session keep it). A locked section still refuses the IPO. `run < count` on join now means only "an older version ran an IPO".
2. **Case 1 with several missed IPOs** (run 0, count 4): one completion only (the one company the section knows; the card says IPO `run + 1`), then `run = count`. The other IPOs had no company, so there is nothing to stamp. *Question:* fine?
3. **What the card holds when the company was completed by the run check:** `ratio`, `shares` and `owned` are unknown then (0, 0, empty); `stake` comes from the saved `rounds` (`CompanyConfig.stakeOf`).
4. **`picked` after case 1.** The doc says the new company has `picked = false`, and the missing-section rule says `picked = true` while the picker is off. I used one rule for every new founding: `picked = not SectorConfig.PickerEnabled`. *Question:* PR 4 needs to say what the picker does with `picked = false` when it is off (nothing today reads it).
5. **Unknown item ids are kept, not skipped.** *Approved by the owner (owner default confirmed), and extended in the review fix.* The doc lists "unknown or duplicate id" among the bad values to skip. But an `objects[i]` or a `stored` id this version has no item for is exactly what a newer version writes (a Gaming upgrade), and CLAUDE.md says never delete what you don't know (one-line exception for the pokedex added to CLAUDE.md). So: well-formed but unknown ids are **kept** (they have no footprint here, so they block nothing, but they count toward the limit of 40); malformed entries and repeated ids are skipped with a warning. Entries over the limit of 40 are skipped (a newer version with a bigger limit would lose them on a rollback). The review fix goes one step further, to keep at every level: a `stored` value other than `true` (a newer version's record, or `false`) is kept as it was and only `== true` means "in storage" (inventory, Sync, Store); and placed items that are not a plain list (a key that isn't 1, 2, 3 ... in a row, also in a card) keep the **whole section as it was** (locked, the IPO is refused), because a list can't carry such keys back to the save. *Fix C narrowed this: only a table with ONLY string keys locks now; a list with a gap or extra keys is tidied on load (see the fix C notes).* Still skipped, on purpose: a malformed entry (bad coordinate, bad turn, id not a short string), a repeated id, a `stored` key that isn't a string of 1 to 39 characters, and everything over 40.
6. **Company names for Software** (`SectorConfig`) are 12 placeholders of mine: the content bible has no company-name list yet. *Question:* approve or rename.
7. **"Budgets" in the checks list** (CUST 4): only the limits that exist in PR 1 are enforced (40 placed items, 40 stored). The part budget (260 per room now, 320 proposed) can't be measured on the server without drawing the objects (PR 3). *Question:* none now; PR 3 adds it.
8. **Footprints of the six upgrades** are the boxes around their `PlotArt` props, centered on x, z (the Desk's prop is not exactly centered; the box is symmetric and a test checks that it holds every part). The building sizes (60 x 60 to 78 x 82) are the doc's estimates. Reserved zones come from `PlotVisuals.zones` for the 60 x 60 plot and do not grow with the building (PR 2).
9. **`Sync` has no definition in the doc.** I made it return the office as the server has it: sector, building and its size, placed items, stored ids, and the reserved zones from the anchor, so a client can preview a placement with the same `CompanyConfig.checkPlacement`.

## Deviations from the doc

- **The three office requests work only in Studio** (`CompanyConfig.Placement = { Enabled, StudioOnly = true }`, like `TaskConfig`). The doc doesn't say; nothing draws a placed object until PR 3 and no client exists, so a live server accepting writes would be saved data nobody can see. A live server answers "Not available yet".
- **A request limit as a bucket:** 4 requests a second per player, a burst of 4 (the doc says "4 requests/s").
- **Overlap "<= 0.1 stud"** is measured as how deep two footprints overlap (separating axis test, 45 degree turns), not as an area.
- **Locked sessions (a newer `v`).** The doc lists GoPublic, Place, BuyBuilding, PickSector and Raise as refused. PR 1 has GoPublic and Place; I also refuse **Store and Sync** (they read or change a section this version can't interpret). GoPublic is refused in `TycoonCore.commitIpo` (I did not touch IpoServer), so the player sees IpoServer's generic "The IPO couldn't be saved. Nothing changed: try again in a moment" and the Output has the real reason. *Also locked:* an active company in a sector this version doesn't know, and a section that threw while loading (kept as it was; a bug can never delete data). A bad `v` (0, -1, 1.5, "2", NaN, ...) is **not** locked: it is skipped with a warning and read as version 1.
- **`name` is not checked against the sector's list on load** (only that it is a string of 1 to 60 characters). It will be checked when it is picked (PR 4).
- **`building`** accepts any whole number from 1 to 99 (a newer version may have more than five); only 1 to 5 have a size, so a larger one can't place anything.
- **`CompanyConfig.Funding.DilutionCap = 4000`** (a placeholder from FUND) exists only because the card's `stake` needs it; PR 4b adds the rest of `Funding`.
- **The three tests the doc says break were updated in the phase 2 commit, not phase 3,** so every push had a passing `tools/daily_test.py`. Phase 3 holds the new ordering and pin tests.
- **`pokedex.studio` is set by every Studio save from PR 1 on** (the doc describes it for the leaderboard in 1.6); a Studio save never clears it.
- A saved `stamp` above 0 with `state = "progress"` is left as it is (the doc only says `"done"` with stamp 0 becomes 1). `sectors[k]` that isn't a table is skipped.

## Not done on purpose (later PRs)

`BuyBuilding`, `roomOf`, the picker window and `PickSector`, the IPO transform and the seed, funding rounds (`Raise`, `dilutedShares`, `dust` is only kept), stamps beyond Bronze, `BoardServer`, every client, `economy_sim.py`. `Buildings.Enabled` and prices are PR 2.

## A process problem you should know about

While this work was running, **another session (the sims session) switched the shared working folder to its branch `sims-two-sectors`**. Two of my commits (the claim and phase 1) were made on and **pushed to `origin/sims-two-sectors`** before I noticed. I did not reset or force anything: I made a second working folder (`../startup-to-ipo-customize-pr1`) on `customize-pr1`, cherry-picked the two commits there and carried on. `origin/sims-two-sectors` still carries my two commits (`95e30cc`, `c84a278`) on top of its own claim commit `f67ee5c`; they add `CompanyConfig.lua`, `SectorConfig.lua`, test code in `tools/daily_test.py` and claim rows in `CONTRIBUTING.md`. They are harmless but they don't belong there. To remove them someone with the right to rewrite that branch has to reset it to `f67ee5c` and force-push it (I won't). `tools/economy_sim.py` was never touched by me.

## Review fix notes (branch `customize-pr1-fix`, independent review of `customize-pr1` at `5e1ae31`)

**Owner defaults.** Four choices in PR 1 are the owner's defaults, not facts of the design: **(1)** `pokedex.run` follows the IPO count for IPOs done before PR 4 (no Bronze stamp, no card, no sector completion until PR 4 turns stamps on); **(2)** unknown item ids (and unknown values and fields) are kept and written back, never skipped; **(3)** the Software company names in `SectorConfig` are placeholders; **(4)** the limit of 40 placed and 40 stored items is applied on load (entries over it are skipped with a warning), and the part budget is skipped on load (PR 3). Change any of them only with the owner.

**For later PRs (nothing to do in PR 1):**
- **PR 2: `zonesCache` must be keyed by building.** `CompanyServer` computes the reserved zones once, from the 60 x 60 layout (`CompanyServer.lua`, `zonesCache`, the `zones()` helper), and reuses them for every request. They don't grow with the building, so a bigger building (60 x 60 to 78 x 82) would be checked against the first room's zones. PR 2 keys the cache by building number (or measures the zones per building).
- **Names are placeholders and not freely renameable once PR 1 is published.** Every new founding gets the sector's first name (`"Garage Labs"`, `SectorConfig`'s list, via `defaultName`) and that name is saved in `active.name` and on cards. Changing or reordering the list later doesn't change a saved name. PR 4 must therefore **accept a saved name that is not in the list** (PR 1 already only checks that it is a string of 1 to 60 characters on load).
- **PR 3: saved layouts over the part budget.** PR 1 saves up to 40 placed items and can't measure parts (nothing is drawn yet). When PR 3 draws objects and enforces the budget (260 parts per room today, 320 proposed), it must decide what happens to a saved layout that is already over it (draw what fits and keep the rest in storage is the safe candidate; never delete).
- **IPO message for a locked section.** The generic "The IPO couldn't be saved. Nothing changed: try again in a moment" stays for a locked pokedex (the reason is only in the server log) until `IpoServer` can show its own message; `IpoServer` was not touched in PR 1 or in this fix.
- **Run follows the count only until PR 4.** `CompanyServer.writeIpoRun` / `onIpo` are replaced by PR 4's IPO transform (which completes the company, stamps and writes the card). Remove them there, together with their tests.

## Review fix B notes (branch `customize-pr1-fix-b`, Opus review of `customize-pr1` at `64ff17d`)

**Owner defaults recorded (accepted by the owner).**
- **(a) An IPO on `main` after a rollback.** If a player who already has a `pokedex` section goes public on a version without PR 1 (for example `main` after a rollback), their `ipo.count` rises and `pokedex.run` stays frozen. At the next join with PR 1 the run check completes the company: Bronze for its sector (if it had none) and a card, once. Accepted. (`run < count` means only that.)
- **(b) A locked player on a live server.** A player whose `pokedex` is locked (a newer `v`, an unknown sector, placed items that are not a plain list, or a section that failed to load) can't go public on this version. They see IpoServer's generic "The IPO couldn't be saved. Nothing changed: try again in a moment." until IpoServer has its own message; the reason is in the server log ("Not going public for <name>: their pokedex is kept as it is ..."). Accepted. **The lock is not Studio-only:** it applies on live servers too (only the three office requests `Place`, `Store`, `Sync` are Studio-only). `tools/daily_test.py` now proves it at runtime (an IPO with a locked section returns false, changes nothing, saves nothing).
- **(c) `card.owned` keeps its extras.** *Superseded in review fix C (below): `card.owned` is now tidied on load, not kept.* The list is read up to its first gap and every other key (a name under a key such as `future`, or an entry after a gap such as `[5]`) is kept as a copy and written back unchanged, like the other maps. Only a value inside the list that is not a name (not a string, empty, over 39 characters) or a name past 200 is skipped, with a warning.

**What this fix changed.** (1) `commitIpo` is tested at runtime with the real `save()`, a fake DataStore and the real `CompanyServer` (markers `SAVEFN` and `COMMITIPO` in `TycoonCore`: comments only). (2) An IPO by this version with unknown fields in the section (top level and every level below it) still writes `run`, moves it in memory and writes every unknown field back unchanged. (3) `card.owned` as in (c). (4) `CLAUDE.md`'s pokedex exception says what is really dropped.

**Loops that drop silently (item 3's check).** In the Pokedex code only `readOwnedNames` did (fixed). `readObjects` also loops `1..#value`, but a key outside the list sets `ctx.foreign` and keeps the whole section as it was (locked, with a warning), so nothing is lost; every other reader uses `pairs` and either keeps unknown keys or warns (a non-string key in a map, a bad value of a known key). A new test adds an unknown key (a string, `99`, `0`, `-3`) to every table of the section: it comes back unchanged or a warning says why (156 cases; the number keys in the maps are skipped with a warning). The older modules read their saved lists with `ipairs`, which stops at the first gap and ignores other keys without a warning: `TycoonCore.sanitizeSave` (`owned`), `ShopServer` (`receipts`), `EmployeeServer` (`employees`, `incubators`), `PoachServer` (`losses`), `OnboardingServer` (`goals`). These are plain lists written only by this code, they predate PR 1 and CLAUDE.md's A10 rule already says older code drops unknown fields inside a section it knows, so **nothing was changed there** (not in PR 1's files); they are listed here for a later pass.

**Open question: what does DataStore `SetAsync` do with mixed or holed tables?** *Fix B wrote `card.owned` extras back as they were; fix C (below) tidies them on load instead, so this question no longer decides anything in the code, but the answer is still worth having (it says whether the tidy was needed, and whether such a table could ever come out of a store).* **Nothing was run in Studio.** The block below replaces the first version (fix C): it stops with a message if `GetDataStore` fails; reads with the cache off (`DataStoreGetOptions.UseCache = false`); runs 13 cases, including the review's exact `{"Desk","Laptop",future="GamingRig",[5]="Neon Logo"}`, the same table at the full path `pokedex.sectors.Software.card.owned`, and two controls (a clean list, and the same path with a clean list); for each case that was stored it writes back exactly what came back (second pass, a second throwaway key); the case loop is inside a `pcall`, and the cleanup calls `RemoveAsync` on **every** throwaway key (both passes, also the ones whose write failed). It uses a throwaway DataStore name and throwaway keys (an `assert` refuses `StartupTycoon_v1` and any `player_` key), never publishes, and prints one line per case. Paste it into Studio's command bar (Game Settings > Security > Enable Studio Access to API Services, and the place published). **It was syntax-checked and run only in the plain Luau tool against a fake Roblox (a fake store that refuses mixed tables and holes, and a fake that fails `GetDataStore`, and one that fails in the middle of the loop: the cleanup ran every time); it was never run in Studio.**

```lua
local DataStoreService = game:GetService("DataStoreService")
local HttpService = game:GetService("HttpService")

local STORE_NAME = "ThrowawayMixedTables_DeleteMe" -- a throwaway name: NEVER StartupTycoon_v1
local KEY_PREFIX = "throwaway_mixed_" -- NEVER player_<UserId>
assert(STORE_NAME ~= "StartupTycoon_v1" and not string.find(KEY_PREFIX, "^player_"), "use a throwaway store and key")

local okStore, store = pcall(function()
	return DataStoreService:GetDataStore(STORE_NAME)
end)
if not okStore then
	warn("STOP: no DataStore (turn on Game Settings > Security > Enable Studio Access to API Services, publish the place, run this again): " .. tostring(store))
	return
end

local NO_CACHE = Instance.new("DataStoreGetOptions") -- read what is really stored, never a copy kept in memory
NO_CACHE.UseCache = false

local function pokedexWith(owned) -- the full path of the save: pokedex.sectors.Software.card.owned
	return { pokedex = { v = 1, run = 1, active = { sector = "Software" }, sectors = { Software = { state = "done", stamp = 1, card = { name = "Old Co", owned = owned } } } } }
end

local CASES = {
	{ "control: a clean list", { "Desk", "Laptop" } },
	{ "review case {Desk, Laptop, future, [5]}", { "Desk", "Laptop", future = "GamingRig", [5] = "Neon Logo" } },
	{ "{[1]=a, [3]=b}", { [1] = "a", [3] = "b" } },
	{ "{[1]=a, [3]=b, [4]=c}", { [1] = "a", [3] = "b", [4] = "c" } },
	{ "hole {Desk, nil, Laptop}", { "Desk", nil, "Laptop" } },
	{ "keys 0 and -3 next to a name", { "Desk", [0] = "Zero", [-3] = "Minus" } },
	{ "{Desk, [\"1\"]=x} (string key \"1\")", { "Desk", ["1"] = "x" } },
	{ "list plus a string key", { 1, 2, 3, foo = "x" } },
	{ "list with a hole {1,2,[5]}", { [1] = "a", [2] = "b", [5] = "c" } },
	{ "only [2]", { [2] = "a" } },
	{ "key 1.5", { [1.5] = "a" } },
	{ "nested pokedex.sectors.Software.card.owned (review case)", pokedexWith({ "Desk", "Laptop", future = "GamingRig", [5] = "Neon Logo" }) },
	{ "nested control: the same path with a clean list", pokedexWith({ "Desk", "Laptop", "Neon Logo" }) },
}

-- every throwaway key, made up front, so the cleanup removes ALL of them (also the ones whose write failed)
local keys = {}
for index = 1, #CASES do
	keys[index] = { first = KEY_PREFIX .. index, again = KEY_PREFIX .. index .. "_again" }
end

local function describe(value) -- one line: every key with its type, sorted
	if typeof(value) ~= "table" then
		return tostring(value)
	end
	local parts = {}
	for key, inner in pairs(value) do
		local shown = (typeof(key) == "number" and ("[" .. key .. "]") or ("s:" .. tostring(key))) .. "=" .. describe(inner)
		table.insert(parts, shown)
	end
	table.sort(parts)
	return "{" .. table.concat(parts, ",") .. "}"
end
local function short(text)
	text = tostring(text):gsub("%s+", " ")
	return #text > 90 and (text:sub(1, 87) .. "...") or text
end
local function json(value) -- "ok", or the start of the error
	local ok, text = pcall(function() return HttpService:JSONEncode(value) end)
	return ok and "ok" or ("ERROR " .. short(text))
end

local rows = {}
local function runCases()
	for index, case in ipairs(CASES) do
		local label, value = case[1], case[2]
		local row = { label = label, json = json(value), set = "?", back = "-", again = "-" }
		table.insert(rows, row)
		local okSet, setError = pcall(function() store:SetAsync(keys[index].first, value) end)
		if not okSet then
			row.set = "ERROR " .. short(setError)
		else
			row.set = "ok"
			local okGet, got = pcall(function() return store:GetAsync(keys[index].first, NO_CACHE) end)
			if not okGet then
				row.back = "ERROR " .. short(got)
			else
				row.back = describe(got)
				-- second pass: write back exactly what came back (this is what a save does after a load)
				local okAgain, againError = pcall(function() store:SetAsync(keys[index].again, got) end)
				row.again = okAgain and "ok" or ("ERROR " .. short(againError))
			end
		end
		task.wait(0.5)
	end
end

local okRun, runError = pcall(runCases) -- whatever happens in there, the cleanup below runs

local removed, failedRemovals = 0, 0
for _, pair in ipairs(keys) do -- RemoveAsync on EVERY key, not only the ones that worked
	for _, key in ipairs({ pair.first, pair.again }) do
		local okRemove, removeError = pcall(function() store:RemoveAsync(key) end)
		if okRemove then
			removed += 1
		else
			failedRemovals += 1
			warn("could not remove " .. key .. ": " .. short(removeError))
		end
		task.wait(0.3)
	end
end

print("== RESULT (store " .. STORE_NAME .. ", reads with the cache off). Columns: case | SetAsync | what GetAsync returned | writing that back with SetAsync | HttpService:JSONEncode of the input ==")
for _, row in ipairs(rows) do
	print(string.format("%-55s | set %s | back %s | again %s | json %s", row.label, row.set, row.back, row.again, row.json))
end
print("== " .. #rows .. " of " .. #CASES .. " cases ran; removed " .. removed .. " keys, " .. failedRemovals .. " removals failed ==")
if not okRun then
	warn("the cases stopped early: " .. short(runError))
end
```

## Review fix C notes (branch `customize-pr1-fix-c`, independent review of `customize-pr1` at `7f968b9`)

**Owner decisions (recorded).**
- **Tidy `card.owned` on load.** A list is rebuilt as a plain list 1 to n: every valid name goes in, in key order, including the names after a gap (`owned` is a set of names, so nothing is lost); any other key is dropped with a warning (a string key while the list has names; 0, a negative or a fractional number); a table with ONLY string keys is kept as it is. Duplicates, values over 39 characters and more than 200 names behave as before, with the same warnings. A stamp above 3 stays clamped (3).
- **Nobody edits saves through Open Cloud.** So a mixed or holed table cannot come out of a store (if the reviewer's reading of `SetAsync` is right, no version could have written one); the tidy is a safety net, and it keeps the tests honest (the test store is now as strict as the reviewer says the real one is).
- **No locked-player IPO message before PR 4.** A locked player still sees IpoServer's generic "The IPO couldn't be saved" until PR 4.

**What each loader does with a table that can't be stored (the cases checked, in `CompanyConfig.lua`).**

| Table | Shape it can carry | Written back |
|---|---|---|
| `card.owned` | list of names | tidied: plain list 1 to n, key order, gap closed (warning), other keys dropped (warning per key). Only string keys and no names: kept as it is |
| `objects` (active and card) | list of `{ id, x, z, r }` | the same tidy (entries read in key order, gap closed, other keys dropped, warnings). **New in fix C:** a list with a gap or extra keys no longer locks the section (it is something the store refuses). A table with ONLY string keys is a map this version doesn't know and the store can hold: the whole section is kept as it was (locked), as before |
| `objects[i]`, `rounds[k]`, `sectors[k]`, `card`, `active`, the section | map, named fields plus unknown fields (`copyUnknown`) | **New in fix C:** an unknown key that is not a string (a number: 99, 0, -3, 1.5) is dropped with a warning; unknown string keys are kept as before |
| `decor`, `kept`, `passSeconds`, `told`, `hall`, `stored`, `rounds`, `sectors` | maps of string keys (`readMap`, `readStored`, `readRounds`, `readSectors`) | already fine: a key that is not a string was skipped with a warning before; the written table has only string keys |
| `sx`, an unknown sector, an unknown stage, an unknown value in a map, a locked section's raw | opaque (`deepCopy` / the saved table as it was loaded) | kept whole, as it came from the store. Not tidied: this version doesn't know its shape, and what came out of a store can be stored again |

`CompanyConfig.completeCompany` copies `extra.owned` into the card for PR 4: **PR 4 must pass a plain list of names** (nothing calls it with one today).

**What the tests do now.** The fake `SetAsync` refuses, like the reviewer says the real one does, a table that mixes list and string keys and a list with holes (or keys 0, negative, fractional), recursively through the whole payload (and a function value, and a table that contains itself). It is used where a payload goes to `SetAsync` (the `commitIpo` / `save()` test, including the locked-section runtime test, and the `buildPayload` test) and as a screen on every section any test serializes (the Pokedex loader's `toSave`, `CompanyServer.serialize`, and `DailyServer`, `IpoServer`, `TaskServer` and `fixedHires` serialize); there is a named check that the fake itself refuses each bad shape. The locked-section tests now use a storable unknown shape (a map) where they used a mixed table, because the store can't hold a mixed one.

**Order of the merges.** The docs PR first, then the sims PR, and `customize-pr1` **last, after the Studio test** (the command-bar block above and the steps in docs/STUDIO_SYNC.md (d)). A small conflict in the claim rows of CONTRIBUTING.md is expected between the branches; the second branch to merge must re-run `python3 tools/daily_test.py` (the claim rows are the only thing that should conflict).
