# Startup to IPO

A Roblox idle tycoon, published as **Build your Startup!** (place `86395856666175`, universe `10768772528`).

Each player gets a garage plot and buys upgrades in the shop's Office tab to earn Cash every second (nothing in the garage is bought by walking onto it). While they're offline they keep earning at 50%, for up to 8 hours. Recruiting eggs hatch creature employees who walk around the garage and add income. A shop sells game passes and developer products. Players can poach employees from each other in the same server and defend with an HR Department or a Poach Shield. Everything the startup earns raises its valuation through five funding stages; at IPO-ready the player can go public (rebirth) for a permanent income multiplier and Shares to spend on permanent perks.

| Milestone | What | Status |
|---|---|---|
| 1 | Garage plot, upgrades, Cash per second, saving, offline income | Done |
| 2 | Recruiting eggs, 3 incubators, 12 creature employees, team slots | Done. Egg shop items stay off sale until `ShopConfig.EggsEnabled = true` |
| 3 | Shop: 4 game passes, 5 developer products | Done |
| 3 (poaching) | Poach employees from other players, HR Department pad, Counter-Offer, Headhunter pass, Poach Shield product | Done. Headhunter and Poach Shield have their IDs and are on sale |
| 4 | IPO rebirth: valuation, funding stages, Go Public, Shares, IPO shop perks, in-server leaderboard, Shareholder pass | Done (PR open). The Shareholder pass shows "Coming soon" until the owner runs the sync (`id = 0`) |
| 5 | First minute: free egg for new players, glowing arrow, goal tracker | Done |
| 6 | Daily rewards: 7-day login calendar (UTC days, one missed day allowed), gift chip next to the valuation bar | Built, waiting for the Studio playtest (branch `milestone-6-daily-rewards`) |
| Customize PR 1 | The company and its Pokedex: a new optional `pokedex` save section (the whole format, four sector keys), `CompanyServer`, `CompanyConfig`, `SectorConfig`; invisible to players (the picker is off, the office requests work in Studio only) | Built on branch `customize-pr1`, waiting for the Studio sync (docs/STUDIO_SYNC.md addendum (d), docs/CUSTOMIZE_PR1_NOTES.md) |
| Visuals | Plot visuals: the garage grows through five rooms as the startup passes each funding stage (stage 1 to 5 built as data in `PlotArt`; no walk-on pads, upgrades are bought in the shop's Office tab) | Built on branch `visuals-garage`, waiting for the Studio check (docs/PLOT_VISUALS.md, docs/STUDIO_SYNC.md) |

## Folder structure

Every Studio script has one `.lua` file here with exactly the same name. The repo is the official copy of the code, and Team Create is the live place (see [Keeping Studio and the repo in sync](CONTRIBUTING.md#keeping-studio-and-the-repo-in-sync)).

| File | Where it goes in Studio | Type | What it does |
|---|---|---|---|
| `TycoonCore.lua` | ServerScriptService | Script | Plots, upgrades, Cash, offline income, saving and loading. Owns all player data. |
| `ShopServer.lua` | ServerScriptService | ModuleScript | Game passes, developer products, VIP perks, Studio Debug tab |
| `EmployeeServer.lua` | ServerScriptService | ModuleScript | Eggs, incubators, hatch rolls, team slots, employees in the garage |
| `PoachServer.lua` | ServerScriptService | ModuleScript | Poaching negotiations, protection and shields, Counter-Offers, the HR Department (bought in the Poach window) |
| `IpoServer.lua` | ServerScriptService | ModuleScript | Valuation, funding stages, going public (IPO), Shares, the IPO shop, the garage's funding sign |
| `OnboardingServer.lua` | ServerScriptService | ModuleScript | First minute for new players: the one free egg, where the arrow points, which goals are finished |
| `DailyServer.lua` | ServerScriptService | ModuleScript | Daily login calendar: which UTC day it is, the streak, the Claim action and its rewards |
| `TaskServer.lua` | ServerScriptService | ModuleScript | Task engine (PR 1: customer calls, **Studio only**): when a call rings (not before the player owns the Desk, or has done an IPO), grading an answer, the reward, engaged time, the measurement numbers for gate G1 |
| `CompanyServer.lua` | ServerScriptService | ModuleScript | The company and its Pokedex (customize PR 1, invisible): the `pokedex` save section on join and save, and the Studio-only office requests Place, Store and Sync. Never touches Cash or the valuation |
| `PlotVisuals.lua` | ServerScriptService | ModuleScript | Builds each player's plot room and the upgrade props from `PlotArt` (looks only), and checks a room against the reserved gameplay zones, part and light budgets |
| `PlotArt.lua` | ServerScriptService | ModuleScript | The art as data: one room per funding stage (Garage, Seed, Series A, Series B, IPO-ready, built from Parts on the same 60 x 60 plot), the hire desks, the six upgrade props |
| `ShopConfig.lua` | ReplicatedStorage | ModuleScript | Every pass and product: name, price, ID, plus the `EggsEnabled` switch |
| `CreatureConfig.lua` | ReplicatedStorage | ModuleScript | Creatures, rarities, eggs, odds, slot counts, poaching rules (`CreatureConfig.Poaching`). Game balance lives here. |
| `CreatureModels.lua` | ReplicatedStorage | ModuleScript | Builds each creature's placeholder 3D model |
| `IpoConfig.lua` | ReplicatedStorage | ModuleScript | IPO rules: stage thresholds, multiplier and Shares formulas, cooldown, IPO shop perks |
| `OnboardingConfig.lua` | ReplicatedStorage | ModuleScript | First-minute settings: the free egg, the goals, when the arrow and tracker end, an on/off switch |
| `DailyConfig.lua` | ReplicatedStorage | ModuleScript | Daily calendar: the 7 rewards, grace days, Cash caps, reset hour (UTC), texts, an on/off switch |
| `TaskConfig.lua` | ReplicatedStorage | ModuleScript | Task rules: one row per task (gap, time limit, reward, team share, when it starts: the Desk), rungs, reward budget, the `Enabled` and `StudioOnly` switches |
| `SectorConfig.lua` | ReplicatedStorage | ModuleScript | The four sector keys (only Software can be picked), the picker switch (off), company names, Hall of Fame goals |
| `CompanyConfig.lua` | ReplicatedStorage | ModuleScript | The Pokedex format and its loader (bad values, unknown fields kept, version, run check), the placement rules and limits, the `Placement` switch (Studio only). Create `SectorConfig` first |
| `ShopClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | SHOP button, shop window, pop-up messages, Debug tab |
| `EmployeeClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | EGGS and TEAM buttons, Recruiting window, hatch reveal, employees walking |
| `PoachClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | POACH button, Poach window, negotiation mini-screen, "you're being poached" alerts, Counter-Offer card |
| `IpoClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | IPO button, valuation bar, IPO window (Go Public with a two-step confirm, Shares Shop, Leaderboard) |
| `OnboardingClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | New players only: the glowing arrow and the goal tracker card under the valuation bar |
| `DailyClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | Gift chip next to the valuation bar, Daily Rewards window (7-day calendar, Claim button) |
| `TaskClient.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | The phone tray: up to 3 waiting calls with an Answer button each, "Tap to resume". Shows nothing until the Desk is owned (or after the first IPO). Does nothing outside Studio in PR 1 |
| `ChatTags.lua` | StarterPlayer > StarterPlayerScripts | LocalScript | Shows the `[VIP]` tag in chat |

Other files:

| File | What it is |
|---|---|
| `sync_monetization.py`, `sync_monetization.bat` | Create and update the passes and products on Roblox from `ShopConfig` |
| `icons/` | Pass icons that `sync_monetization` uploads |
| `tools/economy_sim.py` | Economy simulator (Python): IPO timing, Shares, passes and the daily calendar (`--daily`). See `docs/ECONOMY.md` |
| `tools/daily_test.py` | Logic tests (daily calendar, saves, shop, eggs, IPO, the task engine and its tray layout, the Pokedex rules and CompanyServer, source checks on the money paths, and mutation runs that prove the tests can fail): runs the real server code with a fake Roblox. Needs the free `luau` tool (instructions inside) |
| `docs/PLOT_VISUALS.md` | The five plot rooms, the rules every room keeps and how to add one |
| `docs/STUDIO_SYNC.md` | What exists only in Studio (script hashes, Lighting and Baseplate settings) and the Mac steps to sync it |
| `CONTRIBUTING.md` | How we work together, plus the **Ownership** table (who is editing which script) |
| `CLAUDE.md` | Rules Claude Code follows in this project |
| `.env` | Your Roblox API key. You create it yourself, and it is never committed. |

## Running sync_monetization

It reads `ShopConfig`, then creates or updates all passes and products on Roblox and writes any new IDs back into `ShopConfig`. It's safe to run again: it matches items by ID or by exact name, so it never makes duplicates. It only uses built-in Python and never prints your key.

**You need:**
- Python 3
- A `.env` file in this folder containing `ROBLOX_API_KEY=<key>` (see [Creating an API key](#creating-an-api-key))
- On Windows: Studio open on this place in Edit mode (not playtesting), so new IDs go straight into Studio. Without Studio, it uses `ShopConfig.lua`.

**Windows:** double-click `sync_monetization.bat`. To see what it would do first, open a terminal in the folder and run:

```
python sync_monetization.py --dry-run
```

**Mac:** open Terminal in the folder and run the commands below. The Mac version can't talk to Studio, so it reads and updates `ShopConfig.lua`. If any IDs changed, paste `ShopConfig.lua` into Studio's `ShopConfig` afterwards.

```
python3 sync_monetization.py --dry-run
python3 sync_monetization.py
```

| Option | What it does |
|---|---|
| (none) | Create or update everything |
| `--dry-run` | Only show what would happen. Changes nothing. |
| `--no-studio` | Use `ShopConfig.lua` only and don't touch Studio |
| `--update-icons` | Re-upload the pass icons from `icons/` |

**Egg items:** while `ShopConfig.EggsEnabled = false`, the four egg items (Extra Employee Slots, Auto-Hatch, Luck Boost, Instant Hatch) are kept off sale. Set it to `true` in Studio and in `ShopConfig.lua`, then run the sync, and they go on sale. The switch is `EGG_ITEMS_FOLLOW_EGGS_ENABLED` at the top of the script.

If the sync changed `ShopConfig.lua`, commit it like any other change (on a branch, through a pull request).

### Creating an API key

This is a personal game, so normally only its owner can create a key that works for it. For now, only the owner runs the sync. If you both need to run it, the game would have to move to a Roblox community (group); decide that together first.

1. Go to [create.roblox.com](https://create.roblox.com), then **Open Cloud → API Keys → Create API Key**.
2. Under **Access Permissions**, add **Game Passes** and **Developer Products**. For both, pick **Build your Startup!** and tick **read** and **write**.
3. Under **Security**, add your IP address, or `0.0.0.0/0` to allow any.
4. Create the key and copy it. Roblox shows it only once.
5. Put it in `.env` (see step 6 of the setup below). Never paste it into code, Studio, chat or a commit.

## Setup for a new collaborator (Windows or Mac)

### The owner does this once

1. **Invite on GitHub:** open the repo on github.com, then **Settings → Collaborators → Add people**, type your friend's GitHub username and send the invite.
2. **Turn on Team Create:** open the place in Studio and click **Collaborate** at the top right. In older Studio it's **View → Team Create → Turn ON**.
3. **Add your friend in Studio:** go to **File → Game Settings → Permissions → Collaborators**, search your friend and give them **Edit**. For a personal game, Studio only lists your Roblox friends, so add each other as friends first.

### The collaborator does this

1. **Install the tools.**

   | Tool | Windows | Mac |
   |---|---|---|
   | Roblox Studio | [create.roblox.com](https://create.roblox.com) → Start Creating | same |
   | Git | `winget install --id Git.Git -e` | Run `git --version` in Terminal and click **Install** when asked |
   | GitHub CLI | `winget install --id GitHub.cli -e` | `brew install gh` (needs [Homebrew](https://brew.sh)), or the installer from [cli.github.com](https://cli.github.com) |
   | Python 3 (only to run the sync) | `winget install --id Python.Python.3.12 -e` | [python.org](https://www.python.org/downloads/) installer |

   Close and reopen the terminal after installing, so it finds the new commands.

2. **Accept the invite** from GitHub's email, or at [github.com/notifications](https://github.com/notifications).

3. **Log in to GitHub:** run `gh auth login`, then choose:
   1. **GitHub.com**
   2. **HTTPS**
   3. **Yes** (authenticate Git)
   4. **Login with a web browser**

   Copy the 8-character code and press Enter. Paste the code in the browser page that opens, then click **Authorize**.

4. **Tell Git your name.** Use the email on your GitHub account, or your private address from [github.com/settings/emails](https://github.com/settings/emails):

   ```
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

5. **Clone the repo into Documents.** The first line depends on your system.

   Windows (PowerShell):
   ```
   cd $HOME\Documents
   ```
   Mac:
   ```
   cd ~/Documents
   ```
   Then, on both:
   ```
   gh repo clone mattimarca02/startup-to-ipo StartupTycoon
   cd StartupTycoon
   ```

6. **Create your own `.env`** (only if you will run the sync). This file is never shared and never committed. Make a file named `.env` in the `StartupTycoon` folder with one line:

   ```
   ROBLOX_API_KEY=paste-your-key-here
   ```

   - **Windows:** in Notepad, choose **File → Save as**, set **Save as type** to **All files**, and type the name `.env`. If it ends up as `.env.txt`, that works too.
   - **Mac:** run `nano .env`, paste the line, then press **Ctrl+O**, **Enter**, **Ctrl+X**.

   Then run `git status`. The `.env` file must **not** appear in the list.

7. **Open the place in Studio:** start Studio and sign in. Open **Build your Startup!** from the games shared with you, or from Creator Hub use the game's **Edit in Studio**. It opens as a Team Create session: you both edit the same live place.

8. **Read [CONTRIBUTING.md](CONTRIBUTING.md)** before your first change. Claim your scripts in the Ownership table first.

**Mac note:** `.bat` files only work on Windows. On Mac, run `python3 sync_monetization.py` instead.

## Connecting Claude Code to Studio (Mac)

With the Roblox Studio MCP connected, Claude Code can read the place and push `.lua` files straight into Studio scripts, so you don't have to copy and paste them (see [Keeping Studio and the repo in sync](CONTRIBUTING.md#keeping-studio-and-the-repo-in-sync)). Each person sets this up once on their own Mac.

1. **Turn on the MCP server in Studio:** open the place, open the **Assistant** panel, click **⋯ → Manage MCP Servers**, and turn on **Enable Studio as MCP server**.
2. **Register it with Claude Code** (once per Mac, for all projects). In Terminal, run:

   ```
   claude mcp add --scope user Roblox_Studio -- /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
   ```

   If you use Claude Code only in VS Code and Terminal says `command not found: claude`, add the same server to the `mcpServers` section of `~/.claude.json` instead:

   ```json
   "Roblox_Studio": {
     "type": "stdio",
     "command": "/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP",
     "args": []
   }
   ```

3. **Restart Claude Code** (in VS Code: **Cmd+Shift+P → Developer: Reload Window**).
4. **Check it works:** with Studio open on the place, ask Claude Code to list the scripts in the place. It should find **Build your Startup! (placeId: 86395856666175)** and list scripts such as `ServerScriptService.TycoonCore`.

**Rules still apply:** Claude Code only pushes scripts claimed by the person it's working for (see the Ownership table in [CONTRIBUTING.md](CONTRIBUTING.md)), and the `.lua` file in the repo stays the official copy. The MCP needs no API key.
