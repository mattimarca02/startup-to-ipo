# Working together

Two people, one Roblox place (Team Create) and one GitHub repo. These rules stop us from overwriting each other's work.

## The rules

1. **Pull before you start.** Always begin with the latest `main`.
2. **One branch per milestone or feature.** Never commit code straight to `main`.
3. **Never edit the same script at the same time.** Claim a script in the [Ownership](#ownership) table (docs/lanes/claims.md) before touching it, and leave scripts the other person has claimed alone.
4. **Small commits.** Make one commit per working step, with a message saying what changed and why.
5. **Merge through a pull request.** The other person looks at it before it goes into `main`.
6. **Never commit secrets.** `.env` and `.env.txt` are ignored by git. Keep API keys out of code, Studio and chat.

## A change from start to finish

1. **Get the latest `main`:**
   ```
   git checkout main
   git pull
   ```

2. **Claim your scripts.** In the Ownership table, [docs/lanes/claims.md](docs/lanes/claims.md), put your name, branch and date next to each script you'll change. That file is the only thing you may push straight to `main` (lanes also push their own lane file), and a pull request never changes it:
   ```
   git add docs/lanes/claims.md
   git commit -m "Claim EmployeeServer for milestone-4-poaching"
   git push
   ```
   Tell your teammate. If a script you need is already claimed, wait or talk first.

3. **Make your branch.** Use lowercase and dashes:
   - `milestone-<number>-<name>`, for example `milestone-4-poaching`
   - `feature-<name>`, for example `feature-daily-reward`
   - `fix-<name>`, for example `fix-offline-cash`

   ```
   git checkout -b milestone-4-poaching
   ```

4. **Work and test.** Change the scripts, playtest in Studio (F5) and check the Output window for red errors. Keep Studio and the `.lua` files matching (see [the sync rule](#keeping-studio-and-the-repo-in-sync)).

   Studio playtests need **Enable Studio Access to API Services** turned ON (Game Settings > Security). With it off, saves can't load and the 6 s load retry kicks you out of the playtest.

5. **Commit small.** Commit each time something works:
   ```
   git status
   git add EmployeeServer.lua
   git commit -m "Poaching: steal chance depends on rarity"
   ```

6. **Push and open a pull request.** Pull with `git pull origin main` first. Then:
   ```
   git push -u origin milestone-4-poaching
   gh pr create --fill
   ```
   In the description, write what changed and how to test it in Studio.

7. **Review.** The other person reads the **Files changed** tab, tries it in Studio if needed, and approves or comments.

8. **Merge.** On GitHub, click **Squash and merge**, then **Delete branch**. From the terminal it's `gh pr merge --squash --delete-branch`.

9. **Finish up.** Both people run:
   ```
   git checkout main
   git pull
   ```
   Clear your rows in docs/lanes/claims.md and push that straight to `main`.

**If git says CONFLICT or refuses to push,** stop and ask your teammate or Claude Code. Never use `git push --force` on `main`.

## Keeping Studio and the repo in sync

The repo is the official copy of every script. Team Create is the live place we both playtest. Nothing syncs by itself: a change exists in one place until someone copies it to the other.

- **Studio → repo:** once a change works in a playtest, copy the whole script into its `.lua` file and commit it on your branch.
- **Repo → Studio:** when a `.lua` file changes outside Studio (Claude Code, a fix during review, a revert), paste it into the Studio script with the same name straight away, and playtest.
- **Unclaimed scripts** must be identical in Studio and on `main`. If they differ, the `main` version wins.
- **Before merging a pull request,** the author checks that each changed script in Studio matches the pull request.

To copy a script, double-click it in Studio's Explorer, press **Ctrl+A** then **Ctrl+C** (**Cmd** on Mac), and paste it over the whole `.lua` file. For the other direction, paste the file into the script.

If Studio lists your script in the **Drafts** window (**View → Drafts**), right-click it and choose **Commit**, so the live place gets it.

## Ownership

The Ownership table (who is editing which script right now) lives in its own file, **[docs/lanes/claims.md](docs/lanes/claims.md)**, since 2026-10-18. Claim a script there before changing it and clear it when your pull request is merged; add a row when you create a new script. That file is pushed straight to `main` and **never** changed by a pull request, so claims never make a pull request conflict.
