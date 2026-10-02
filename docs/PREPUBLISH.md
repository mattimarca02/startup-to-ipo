# Pre-publish checklist: Build your Startup!

Built on 2026-10-02 from CLAUDE.md, ROADMAP.md, CONTRIBUTING.md, docs/ECONOMY.md, docs/STORE_PAGE.md and the five review files in docs/reviews/. No game code was changed to make it.

**How to read it.** Each item has: what to check, the **pass** condition, the **risk** if skipped for real players (Critical / High / Medium / Low), and **Blocks?** (Yes = don't publish until done; No = can wait until after launch). Risk and Blocks are my judgement; change them if you disagree.

Items marked **(code)** need a small code change first (a `.lua` file, which needs its owner's claim in CONTRIBUTING.md and a Studio sync), then the test.

| Group | Who | Items | Blockers |
|---|---|---|---|
| A | Claude Code, 2-player Studio session (negative-ID players) or repo only | 24 | 10 |
| B | Mattia, by hand in Studio / on a live server / on a phone | 10 | 8 (+ part of B10) |
| C | Roblox dashboard or account | 13 | 10 |
| D | Decisions for Mattia | 8 | 3 |

---

## Finding: the Shares line "59 at IPO 5, 83 at IPO 10" is NOT above the cap-2 ceiling

Source of the line: ROADMAP.md:24, docs/ECONOMY.md:131. I read `tools/economy_sim.py:354-361` against `IpoConfig.lua:157-160`:

- The formula is the same in both: `SharesPerIpo * (1 + 0.8 * IPOs already done) * min(ratio, 2)^0.5 * passMultiplier`. The sim reads `self.ipos` **before** it adds one (`economy_sim.py:359-361`), the same as the game's `ipoCount`. So "IPO 5" means 4 IPOs already done.
- The **ceiling** is the value at ratio = 2 (valuation 2x IPO-ready): IPO 5 = 10 x 4.2 x 1.414 = **59.4 -> 59**. IPO 10 = 10 x 8.2 x 1.414 = **116**.
- So **59 is exactly the ceiling** for IPO 5, not above it, and 83 is **below** the IPO 10 ceiling (116). Its base with no overshoot is 82, so the median ratio there is about 1.02. The Shareholder pass numbers (118 / 166) are the same values x2, and are inside the pass ceiling (119 / 232).
- If "IPO 5" is counted as 5 IPOs already done, the ceiling is 70.7, still above 59. I found no reading where the line is over the cap.
- No change needed to ROADMAP or ECONOMY. One thing worth knowing: the median active player sits **at the cap** at IPO 5 (and nearly at it at IPO 2: 25 of 28). Their offline Cash puts them past 2x IPO-ready, so waiting longer buys nothing. That feeds decision D2 (the hint wording).
- Not re-run: a `--ipo --runs 10 --days 365` run did not finish inside my time limit, so I did not re-measure the medians. The check above is by reading the code.
- Also stale, not wrong: docs/ECONOMY.md sections 3b and 3c still show the old numbers (growth 0.3, cap 4) as history. Section 3d is the final one. A one-line "superseded by 3d" under 3b and 3c would stop confusion (item A21).

---

## Group A: Claude Code can test it (2-player Studio session, negative-ID players, or repo only)

Use negative-ID players only. Never write to a real `player_<UserId>` key. Needs **Enable Studio Access to API Services** ON (CONTRIBUTING.md:41).

| # | Check | Pass | Risk if skipped | Blocks? | Source |
|---|---|---|---|---|---|
| A1 | **Bad saves into the loader.** Write `cash = "abc"`, `cash = nan`, `cash = -5`, `owned = "x"`, a non-table save, and `lastSeen = 0` / `-1` to a negative-ID key, then join. | No kick loop. Warning in Output, safe defaults. A non-table save is not treated as a new player and is not overwritten (R5). | **High**: a corrupt save locks a player out or wipes their progress. | Yes | ROADMAP.md:106; PR14_REVIEW F1; PR14_REREVIEW R5 |
| A2 | **Brand-new player's shield blocks a poach.** Client 1 joins as a new player (free egg), Client 2 tries to poach them in the first 15 min. | Poach is refused with the shield message. After 15 min it works. | **High**: new players lose their first employee in minute 2 and quit (D1 retention). | Yes | ROADMAP.md:106; M5_REVIEW F3 |
| A3 | **Full exploit review of every RemoteEvent.** From a client, call `ShopRemotes`, `EmployeeRemotes`, `PoachRemotes`, `IpoRemotes`, `OnboardingRemotes`, `DailyRemotes` with wrong types, huge numbers, NaN, nil, tables, spam. | Every one is refused cleanly, no server error, no Cash/Shares change, rate limits hold. | **High**: duplicated Cash, Shares or employees. | Yes | ROADMAP.md:68 (M9); CLAUDE.md "Server authority" |
| A4 | **Debug tools cannot run on a live server.** Check every `addDebugAction` and Debug remote is behind `RunService:IsStudio()` and `ShopConfig.DebugInStudio`, including the Daily and IPO debug buttons. | No debug action is reachable when `IsStudio()` is false (read the code, then fire the remotes in a Studio server with the guard forced off in a test copy, not the real script). | **Critical**: any player grants themselves Cash or Shares. | Yes | CLAUDE.md "UI conventions"; ShopServer.lua:525,593 |
| A5 | **Run `python tools/daily_test.py`.** Paste the result into the PR / this file. | The line reads "N passed, 0 failed" (104/104 at last count). | Low (it is the logic test for saves and daily). | Yes (takes a minute, and it is the proof for A1) | PR14_REREVIEW R7 |
| A6 | **Studio vs repo match.** Compare every `.lua` file with its Studio script through the Studio MCP (read only) and report differences. | Zero differences, or each difference explained. `.env` / `.env.txt` not in `git status`. | **High**: an old script goes live (the 4 pending PRs all need syncing). | Yes | ROADMAP.md:110; CLAUDE.md "Studio and the repo" |
| A7 | **Config check.** Every `ShopConfig` item has `id ~= 0` and the price matches Creator Hub (see C5). `EggsEnabled` is what you decided in D4. No config key was renamed since it shipped. | Static script prints a table; zero `id = 0`. | **High**: an item is not buyable or charges the wrong price. | Yes | ShopConfig.lua:8-16; CLAUDE.md "Config-driven items" |
| A8 | **Paid pass check times out (M4 low 1) (code).** If `UserOwnsGamePassAsync` is slow, pay the missing offline Cash when it answers and refuse `GoPublic` until it answers. Test by making the check yield 15 s in a test copy. | Offline Cash is paid in full later; an IPO is refused until the pass check ends. | **Medium**: a paying player permanently misses the Shareholder x2 on an IPO (rare, only when Roblox is slow). | Yes (it is a paid item) | M4_REREVIEW low 1; ROADMAP.md:74 |
| A9 | **`data.saving` can stay true forever (M4 low 5) (code).** Build the payload inside the `pcall`, always clear `data.saving`. Test by forcing a `serialize` error. | Next autosave still runs. | **Medium**: one error would stop all later saves of a player. No trigger exists today. | No | M4_REREVIEW low 5; ROADMAP.md:78 |
| A10 | **Unknown keys inside sections (M4 low 3 and 4).** Add a CLAUDE.md rule: new saved data gets its own top-level section, and new sections re-check themselves against `team` / `ipo` on load. | Rule written. | Low (only on a rollback to older code). | No | M4_REREVIEW low 3, 4; ROADMAP.md:76-77 |
| A11 | **PR14 R3 (code, Studio only).** `finish` in PoachServer checks `poachOf(target) == nil` before the `ignoreShields` branch. | Dummy deal ending during an IPO save does not error. | Low (Studio only). | No | PR14_REREVIEW R3; ROADMAP.md:80 |
| A12 | **PR14 R4 (code).** Reword "got protected" to "X is going public" and fix the comment. | Text matches what happened. | Low | No | PR14_REREVIEW R4; ROADMAP.md:81 |
| A13 | **PR14 R6 (code).** Ignore a `lastSeen` that is 0 / negative / over a year old. Covered by A1. | Offline pay is not the full cap for a bad `lastSeen`. | Low (saves are written by the server). | No | PR14_REREVIEW R6; ROADMAP.md:82 |
| A14 | **PR14 R8 (code).** `IpoServer` `number()` rejects `math.huge`. | `ipo.count = inf` is skipped with a warning. | Low | No | PR14_REREVIEW R8; ROADMAP.md:84 |
| A15 | **PR14 F4 (code).** If `poached()` returns false after a successful roll, refund `negotiation.cost` and say "deal fell through". | Poacher's Cash comes back. | Low (needs a duplicate-ID situation). | No | PR14_REVIEW F4; ROADMAP.md:102 |
| A16 | **PR14 F5 (code).** Add `EmployeeServer.restoreEmployee` for the give-back after a failed move. | Employee returns at its old index, `team.outgoing[id]` cleared, even when the team is full. | Low-Medium (a lost employee in a rare failure). | No | PR14_REVIEW F5; ROADMAP.md:103 |
| A17 | **PR14 F7 and F8.** F7: check `GetRequestBudgetForRequestType` before each load retry. F8: fix the `PoachServer.isBusy` comment (a finished poach holds it up to ~60 s). | No request-budget errors during a simulated outage. | Low | No | PR14_REVIEW F7, F8; ROADMAP.md:104-105 |
| A18 | **M5 Lows F4-F10 (code).** F4 legacy check when `Enabled = false`; F5 retry dismiss during an IPO save; F6 `trackerShown` flag; F7 send toast after `data.ready`; F9 warn on bad onboarding values; F10 card respects `OpenPanel`. (F2 is B4, F8 is D5.) | Each behaves as written in the review. | Low | No | M5_REVIEW; ROADMAP.md:85-93 |
| A19 | **M6 Lows (code).** F2 on Day 7 check `IpoServer.isBusy` before the egg so the day can't be used with only part of the reward; F4 note in Debug row text that it writes the real save; F7 chip waits for the poach panel without a 30 s timeout. | Day 7 is all-or-nothing; texts match. | Low | No | M6_REVIEW F2, F4, F7; ROADMAP.md:98-100 |
| A20 | **Poach refund after a crash (F6).** See D6. If you choose "fix", test by killing the server mid-negotiation. | Per decision. | Low | No | ROADMAP.md:95; M4_REVIEW F6 |
| A21 | **Docs fixes.** (a) "superseded by 3d" under ECONOMY 3b/3c. (b) docs/STORE_PAGE.md:5 and :113 still say the IPO is not built; it is, so the IPO text and thumbnail 4 are unblocked. (c) ROADMAP "Next steps: M5" (line 18) and "merge PR #16" (line 25) are stale. (d) ROADMAP.md:22-23 says the same "Shut down all servers" three times; keep one line. (e) CONTRIBUTING row for OnboardingClient still says @mattimarca02 / milestone-5-onboarding since 2026-10-01 (line 112): clear it if that PR is merged (it is). | Docs match the game. | Low | No (except (b), which feeds C10) | files named |
| A22 | **IPO + poach + daily, full run on 2 players.** Re-run after all code changes above: new player, claim, IPO with an open deal, rejoin, missed days, full incubators, malformed calls. | Same results as the passed M6 / PR #14 playtests, no red errors. | **High** if something regressed. | Yes | M6 status; PR14 status |
| A23 | **Egg odds shown for every egg and Luck Boost** (read the code that builds the odds text, compare to `CreatureConfig`). A visual check is B7. | Displayed numbers = config numbers. | **High** (Roblox policy, and the design rule). | Yes | ROADMAP.md "Design rules"; ECONOMY finding 6 |
| A24 | **Offline "While you were away"** is not built (M6b). Confirm nothing in the UI promises it. | No text refers to it. | Low | No | ROADMAP.md:49-53 |

**Order I'd run group A** (cheapest and most dangerous first, code changes before the final regression):
1. A5 (daily_test.py, 1 minute, proves the save logic)
2. A4 (debug tools, read-only, Critical)
3. A7 (config / IDs, read-only)
4. A1 (bad saves into the loader)
5. A2 (new-player shield)
6. A3 (remote exploit sweep)
7. A8, then A9 (the two code fixes I recommend before launch, each followed by its test)
8. A23 (odds text)
9. A6 (Studio vs repo compare, once all code is final)
10. A22 (full 2-player regression, last, on the final code)
Low items A10-A21 can be batched into one PR after launch.

---

## Group B: Mattia, by hand (Studio on PC / Mac, phone, live server)

| # | Check | Pass | Risk if skipped | Blocks? | Source |
|---|---|---|---|---|---|
| B1 | **M6 chip phone layout.** Test -> Device: 320x568 portrait and 568x320 landscape, goal tracker showing. | Valuation bar, goal card and gift chip all readable; chip tap works; nothing overlaps. Text is not unreadably small (if it is, move the chip under the bar). | **Medium**: first-time phone players (most of Roblox) see a broken HUD. | Yes | ROADMAP.md:106; M6_REVIEW F5 |
| B2 | **API Services OFF kicks the player.** Turn **Enable Studio Access to API Services** OFF, play, wait. | Player is kicked after a few seconds (about 6 s retry), no unsaved session. Turn it back ON afterwards. | **Medium**: if the safety net fails, players play without saving. | Yes | ROADMAP.md:106-107; PR14_REVIEW F6 |
| B3 | **`getStore()` and the catch-up loop on a live server.** After publishing, join the real (still private) game from a second account and read the Developer Console (F9 / server log). | No R1 / R2 symptoms: players who join during startup are set up, none is kicked, saves work on the live server. | **High**: every joiner is kicked, or plays without saving. | Yes | ROADMAP.md:106; PR14_REREVIEW R1, R2 |
| B4 | **Landscape phone: goal card vs poach panels (M5 F2).** Trigger a negotiation / poach alert on 667x375 with the card showing. | Card does not cover the panels (or accept the overlap). | Low | No | M5_REVIEW F2; ROADMAP.md:86 |
| B5 | **Mobile pass on every screen.** Shop, Eggs, Team, Poach, IPO, Daily, onboarding, on 2 phone sizes and one tablet, on a real phone if possible. | Every window opens, scrolls and closes with touch; only one window at a time. | **Medium-High** | Yes | ROADMAP.md:68 (M9); CLAUDE.md "Everything must work on a phone" |
| B6 | **Reset all dev saves, then a clean new-player run on the live game.** Delete dev saves (DataStore), join with a fresh account: free egg, arrow, hatch, buy, goal tracker, daily claim, rejoin. | New player earns, hatches and buys within 60 s without reading anything. | **High**: dev saves and test data in live ranking, or the first minute is broken. | Yes | ROADMAP.md:72 |
| B7 | **Real purchases with a second account.** Buy one Cash pack, one pass (e.g. Shareholder), a Poach Shield; rejoin. | Granted once, saved, survives rejoin, no double grant; prompts show the right price. | **Critical**: money taken and nothing granted, or double grants. | Yes | CLAUDE.md "Never trust the client for purchases" |
| B8 | **Odds visible in-game** for each egg and for Luck Boost, as a player sees them. | Percentages visible before buying, equal to the config. | **High** (policy). | Yes | STORE_PAGE.md:157-169; ROADMAP "Design rules" |
| B9 | **Publish method.** Publish all changes, then use **Shut down all servers**. Then check Output / Developer Console on a fresh server. | No server runs old code; sections `ipo`, `onboarding`, `daily` survive a rejoin on an existing save. | **Critical**: an old server wipes the new save sections (M4 F2). | Yes | ROADMAP.md:11,22-24; M4_REVIEW F2 |
| B10 | **Store assets made.** Icon, 4 thumbnails (thumbnail 4, the IPO, is no longer blocked), 2 order variants, 30 s clip. | Files exist per the briefs, no key / `.env` visible. | Medium (discovery). | No for the clip; Yes for icon + 3 thumbnails | STORE_PAGE.md sections 3-5 |

---

## Group C: Roblox dashboard or account

Start the first four now: they take time.

| # | Check | Pass | Risk if skipped | Blocks? | Source |
|---|---|---|---|---|---|
| C1 | **Roblox Plus for 2+ months, or the refundable fee.** | Requirement shown as met in Creator Hub. | **Critical** for the plan: no payouts / publishing path. Cannot be rushed. | Yes | ROADMAP.md:113-114; STORE_PAGE.md:163 |
| C2 | **ID verification** on the account that owns the game / group. | Verified. | Critical | Yes | ROADMAP.md:113 |
| C3 | **2-step verification** on. | On. | Critical (also protects the account). | Yes | ROADMAP.md:113 |
| C4 | **Group and payouts.** The game is already in the group (universe 10768772528, place 86395856666175). Confirm the group owns it, the second collaborator has the right role, and the payout / DevEx account is set. | Group is the owner, roles right, revenue goes to the group before the first Robux. | **High**: hard to move after revenue starts. | Yes | ROADMAP.md:12,121; STORE_PAGE.md:168 |
| C5 | **Pass price mismatch.** The store page shows 180 / 135 / 225 R$; Monetization / `ShopConfig` has 199 / 149 / 249 (2x Cash 199, Extra Slots 149, VIP 249). I could not find 180 / 135 / 225 anywhere in the repo, so which three passes they are, and where they are shown, needs you. (Note: they are about 90% of the other numbers.) | One price per pass everywhere: Creator Hub, `ShopConfig.price`, store page. `ShopConfig` says Roblox always charges the Creator Hub price; the shop only displays the number. | **High**: players see one price in the shop and are charged another (refund requests, bad reviews). | Yes | ShopConfig.lua:8-9; ROADMAP.md:8 |
| C6 | **Run `sync_monetization` (PC)** if anything changed (new item, price) and confirm every item has an ID. | `ShopConfig` ids all non-zero, match Creator Hub. | High | Yes if C5 changes anything | CLAUDE.md "Config-driven items" |
| C7 | **API key and sandbox notes.** The key lives in `.env.txt` (gitignored). Check its expiry date and that it has access to the **group** universe, not the old sandbox. Rotate it if it will expire soon, and never paste it anywhere. The sandbox copy is archived: make sure it holds no live passes or products people can still buy. `git status` lists no `.env*`. | Key valid for the next 3 months, scoped to the live universe; sandbox has nothing for sale. | Medium: `sync_monetization` fails (or touches the wrong game) on the day you need it. | No (but check before C6) | ROADMAP.md:12,14; CLAUDE.md "Secrets" |
| C8 | **Read Roblox's current policies** in Creator Hub: Paid Random Items, monetization, rewards (daily / login). Confirm the 7-day calendar (no Robux in the daily window, fixed visible rewards, odds shown) and the Robux items that touch random chances (Luck Boost, egg items, Instant Hatch). | Each policy read, and each point confirmed or the game changed. | **High**: the game or an item can be moderated or removed. | Yes | ROADMAP.md:108 |
| C9 | **Age-rating questionnaire.** Mention real-money items, random chances (eggs) and player-to-player interaction (poaching). | Rating assigned. | **High**: a new game needs it to be published. | Yes | STORE_PAGE.md:167 |
| C10 | **Store page upload.** Icon, 4 thumbnails, title, description; add the IPO section now that the IPO exists (STORE_PAGE.md:5, :49 still say it isn't built); remove the "Add this section" note. | All uploaded, text matches the game (3 eggs, 12 creatures, IPO, Daily). | Medium (play-through rate is the #1 discovery signal). | Yes (icon, 3 thumbnails, text) | STORE_PAGE.md |
| C11 | **Thumbnail A/B test** (variant A: 1,2,3,4; B: 2,1,3,4). | Both running. | Low | No | STORE_PAGE.md:121-126, 175 |
| C12 | **Experience settings.** Phone, tablet, PC enabled; max players; genre; private servers decision; "public only when ready". Set to public last, after B9. | Settings set; game is public only after the final test. | Medium | Yes | STORE_PAGE.md:169 |
| C13 | **Age audience note.** New games first reach age-checked 16+ players only (under-16s after 250 plays by engaged players in 60 days). Nothing to click; keep the page tone teen/adult. | Page matches. | Low | No | ROADMAP.md:113 |

---

## Group D: Decisions for Mattia

| # | Decision | Options and cost | My recommendation | Risk if skipped | Blocks? |
|---|---|---|---|---|---|
| D1 | **Shareholder pass strength vs shop size.** The pass (2x Shares, 199 R$) finishes the 525-Share shop in about 2 days (active) vs about 7 without it. The sim does not model perks, which makes real players about 15-25% faster. | (a) Leave it: free, but the best-selling feel and nothing left to buy after week 1, so low late spend. (b) Weaker pass (x1.5): cheap to build, but players who buy it before you change it are right to complain, so only possible now. (c) Bigger shop (more perk levels, higher costs, about 2-3x the total): some config work and a sim re-run; buyers keep what they paid for. | **(c)**, with the pass left at 2x. A pass can't be weakened after sales; a shop can be extended any week. **DECIDED and built (branch launch-decisions, 2026-10-02):** pass stays 2x, the shop is now 1,770 Shares (new levels on Faster Recruiting, Talent Scouts and Recruiter Network; see docs/D1_SHOP_OPTIONS.md). | **High** (a paid item you can't retune later). | Yes (decide now; the bigger shop itself can ship later) |
| D2 | **"Wait longer for more Shares" hint** (IpoClient). It is now false past 2x IPO-ready (`SharesRatioCap = 2`), and the median active player is at the cap at IPO 5 (see the finding above). | (a) Reword to "Waiting past 2x IPO-ready gives no more Shares". (b) Remove the hint. | **(a)**, one line; needs a Studio sync of IpoClient. | Low-Medium (players wait for nothing). | No |
| D3 | **`ResetHourUtc`.** Fixed at 0 UTC now. After launch changing it earlier gives everyone one extra claim, so decide now. | (a) 0 UTC: midnight UTC is about 7-8 pm US Eastern, so the reset lands in the evening for the US and the night in Europe. (b) A quiet hour such as 8 UTC (4 am US Eastern, mid-morning Europe): no real cost, re-run `daily_test.py` and check the window's countdown text. | **(b) 8 UTC** if your players are mostly US / Europe; keep 0 only if you have no data yet. Either way, pick before launch. | Medium: wrong choice can't be changed without a free day for everyone. | Yes |
| D4 | **`EggsEnabled` and the off-sale items.** Now `false`: Extra Employee Slots, Auto-Hatch, Luck Boost and Instant Hatch (all `needsEggs = true`) show "Coming soon". | (a) `true` at launch: all 4 sell; needs C8 and B8 passed first. (b) Stay `false` and flip it in the first weekly update: no policy risk at launch, but the best passes are missing from week 1. | **(a)** after C8, B8 and A23 pass. If any of them fails, ship with (b). | Medium (revenue) or High (policy), depending on the choice. | Yes |
| D5 | **Session locking (F10).** Without it, a player who hops servers fast can: claim the same day twice (M6 F10), get the free egg twice (M5 F8), or undo an IPO (M4 F10). Nothing is duplicated permanently; whichever server saves last wins. | (a) Build it before launch: closes all three, but changes the save loader that every other safety rests on, needs 2-server tests, risks lockouts. (b) Ship without it and build it in the first 1-2 updates. | **(b)** with a note in the release plan. The exposure is small at launch and a rushed lock is a bigger risk than the edge case. Revisit if you see duplicate rewards. | Medium. | No |
| D6 | **Poach refund after a server crash (F6).** An unfinished poach can refund old-run Cash into the new run after an IPO. | (a) Accept and list it as a known low risk (the M4 review recommends this). (b) Fix it with a run id on the refund: more code in PoachServer. | **(a)** | Low | No |
| D7 | **IPO balance retune (F8).** The retune is merged (growth x2.5); the stage x38 / multiplier x3.6 worry from M4 review F8 was the reason. Sim now says IPO 10 at about 6.6 h online. | (a) Close F8 as done after you play IPOs 1-5 and it feels right. (b) Retune again: needs the sim re-run and Studio sync. | **(a)**, and check real numbers at day 7 after launch. | Low | No |
| D8 | **Build more before launch, or publish?** M6b (while you were away, 2x offline product) and M7 (weekly events) are not built. | (a) Publish after groups A-C. (b) Wait for M6b / M7: about 1-2 weeks more, and nothing here depends on them. | **(a)**: the C1-C3 account clocks run in parallel and the first weekly update can be M7. | Low | No |

---

## Blockers: the short list

**Group C, start today (can't be rushed):** C1, C2, C3, C4, C5, C8, C9.
**Group A:** A1, A2, A3, A4, A5, A6, A7, A8, A22, A23.
**Group B:** B1, B2, B3, B5, B6, B7, B8, B9.
**Decisions:** D1, D3, D4.

## Order of publishing day (after the blockers are done)
1. All code merged, scripts synced (A6), `daily_test.py` passing (A5).
2. Publish to Roblox, then **Shut down all servers** (B9). Do it once for all of M4, M5, M6, PR #13 and PR #14, which added the `ipo`, `onboarding` and `daily` sections.
3. Live checks on the still-private game: B3, B7, B6.
4. Store page, then the public switch (C10, C12), then reset dev saves one last time if anything was tested on real saves.

## Can wait for after launch
A9-A21, A24, B4, B10 (clip), C7, C11, C13, D2, D5-D8.
