# Owner requests

Only the owner (or Claude on his behalf) edits this file. Each lane reads it at the start of every run, like the other lane files, and adds the requests addressed to it to its backlog. When a request is done, the lane says so in its own lane file (this file is not edited by lanes).

## Requests to lanes

### building: a cinematic when the company moves to a bigger building (2026-10-17)

When a garage's building changes to the next funding stage (Garage to Small Office, and so on up to Big Corporate), the owner of that garage sees a short cinematic: a crane arrives, its wrecking ball knocks down the old building, then the new building rises out of the ground and settles into place. Put it in your backlog as a high-priority item, right after the item you are doing now.

Rules for it:
- **Client only, looks only** (CLAUDE.md "Client-only visuals"): the server swaps the building exactly as today; the cinematic only animates what the client shows. Nothing is saved, nothing goes through a remote except what already tells the client the stage changed, nothing waits on the client.
- **Short and skippable**: about 5 to 7 seconds, a tap or click skips it, it never plays while a window is open (PlayerGui "OpenPanel") and plays at most once per stage change. Camera control returns to normal at the end, also if the player resets or leaves during it.
- **Never traps anyone**: solid boxes stay the server's; players inside are handled by the existing unstick rule. Other players near the garage see only a simple rise of the new building, not the camera move.
- **Phone first**: smooth on a phone, no lights, a small part budget for the crane (Parts, anchored, no collision), removed at the end.
- **Not after an IPO**: an IPO resets the building to the Garage; that reset does not play the demolition cinematic (a short "fresh start" rise at most).
- Preview it in Blender (frames of the key moments) and put the frames in docs/previews/building/ in the PR. If the crane would look better as a kit model, write it as a request in your lane file; do not add assets yourself.

### all lanes: never lose work if a run stops (2026-10-17)

A run can stop at any moment (for example when the owner's usage limit is reached). So: push your branch to GitHub after every working step (a WIP commit is fine), keep your lane file's "Doing now" pointing at that branch, and when a run starts and your branch already exists on GitHub with unfinished work, continue from it instead of starting over.

### quality: claim rows must stop causing merge conflicts (2026-10-18)

Every lane edits the Ownership table in CONTRIBUTING.md on main all day, so any open PR that touches rows near them goes "dirty" within minutes (PR #40 and PR #44 both did, twice, and the owner had to wait or the lanes could not fix it in time). Please propose, as one docs PR (the owner merges it), a way that ends this: for example the claim rows move out of CONTRIBUTING.md into their own file (`docs/lanes/claims.md`) that no PR diff touches and that lanes push straight to main, with CONTRIBUTING.md, docs/LANES.md and the lane prompts' wording changed to match. Also add one rule to docs/LANES.md: a PR never carries claim-row edits; claim rows only go straight to main. List in the PR what each lane has to change so the manager can pass it on. Do not start before the open PRs (#44 and the batch PRs) are merged.

### quality: finish Batch 1 for Studio (2026-10-18, urgent, before the claim-rows PR)

PR #44 is merged (main has `ClaimButtonClient` sha256 `b00fcd8637d378eca02d3e6b4b856ee9fea8d184ea3086a2031d0eee124817c4`, 10261 bytes), but docs/STUDIO_SYNC_BATCH.md still lists the #35 version (`494d14bd…`, 7525 bytes) in the paste table and the hash block, and #44 under "Coming (provisional)". Studio is run from this doc today, so the hash block would print DIFFERENT. Please update the batch from `main` first: the ClaimButtonClient row and hash in the list and in the hash block, move #44 out of "Coming", header "main at <commit>", no provisional rows left, recompute every hash from main, then push (docs only; the owner merges). Tell the owner in your last report when Batch 1 is final.

### gameplay: the owner's answers to D-A, D-B, D-C (2026-10-18, written OK)

- **D-A: yes, run gate G1 first** (your default). Build nothing of item 4 until G1's numbers are in ROADMAP, or the owner writes "skip G1". Meanwhile do the other backlog items (item 7 and the rest) that do not depend on it.
- **D-B: option (a), a new top-level section** `away = { engagedDay, engagedSeconds, bankSeconds }` (rule A10, KNOWN_SECTIONS, optional on load, its own serialize, Shut down all servers when published). Do not add `bankSeconds` to `tasks`: the rule says a new feature never adds a field to an existing section, and no exception is made. Save-format change: this is the owner's written OK for that section only.
- **D-C: do NOT cut the offline payout as drafted.** Keep today's offline Cash (50% of Income, up to 8 h, paid on join). What the plan has to protect is the IPO valuation, so write the variant: the offline Cash stays, but only 10% of it (or none; propose which in the PR) counts toward the valuation. The CLAIMLOAD block pin must stay byte-identical unless the variant needs a change inside it; if it does, say so in the plan and wait for the owner. After G1, if the numbers say more is needed, propose it then.

### quality: turn the claim on (owner decision 9 changes, 2026-10-18, written OK)

The owner wants players to join the plaza and claim a garage at its "Claim garage" prompt (the ring of six garages), instead of today's row of garages with the join claiming the first free one. This is the owner's written OK to flip the switch in the repo: `LobbyConfig.ClaimEnabled = true`.

Please open one small PR (docs and the one switch, nothing else): (1) `LobbyConfig.lua` `ClaimEnabled = true` and its comments ("ships OFF" becomes "ships ON since 2026-10-18, owner decision 9 revised"); (2) change only what `tools/lobby_test.py` and the other suites pin about the default (run all seven suites one at a time; the CLAIMLOAD block stays byte-identical); (3) CLAUDE.md and docs/PLOT_VISUALS.md wording that says "ships false"; (4) a "Batch 2" section in docs/STUDIO_SYNC_BATCH.md: paste `LobbyConfig` only (hash, bytes), the hash block, Studio test with Test > Local Server and 2 players (each player gets a prompt, claims a different garage, the phone button shows, one player leaves and the garage frees up), then Save to Roblox. Say plainly in the PR that playtest (b) with 2 to 3 players has never been run. Do not publish anything: Publish with Shut down all servers stays the owner's decision after that test.
