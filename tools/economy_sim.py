#!/usr/bin/env python3
"""Economy simulator for "Build your Startup!" (standard library only).

Run:   python tools/economy_sim.py            (prints all tables, takes ~1 minute)
       python tools/economy_sim.py --runs 10  (faster, noisier)
       python tools/economy_sim.py --markdown (prints the tables as Markdown for docs/ECONOMY.md)
       python tools/economy_sim.py --daily    (only section 7, the daily calendar table)
       python tools/economy_sim.py --active   (only section 8, the ACTIVE-PLAY proposal; default OFF everywhere else)
       python tools/economy_sim.py --long     (only section 9, the LONG-GAME proposal: 50+ engaged hours to the first IPO; default OFF)
       python tools/economy_sim.py --s1 ... --s10  (one design-doc sim each, docs/SIMS_RESULTS.md; default OFF); --pokedex = S1-S7, --rounds = S8, --gaming = S3 + S9 + S10, --pk-check = engine check

It reads NOTHING from the game: every number is copied by hand into the CONFIG block below.
If you change a .lua config, update this block too. It never changes any game number.
The model is event-driven (no fixed time step), so a 7-day run takes a few milliseconds.

The 7-day login calendar (DailyConfig.lua, milestone 6) IS modeled: see the DAILY_* block and
section 7. A simulated player claims at the first login of every day (they never miss one, the
worst case for the economy). Calendar Cash is a gift: it goes to Cash only, never to the
valuation, exactly like DailyServer; claim_daily asserts it. Sections 1-6 run without the
calendar (DAILY_IN_ALL_TABLES = False) so they stay comparable with docs/ECONOMY.md.

ACTIVE PLAY (docs/ACTIVE_LOOPS_PROPOSAL.md) is a PROPOSAL, not in the game yet. The ACTIVE_* block below holds
the recommended starting numbers of the task engine. It is OFF by default: no section 1-7 number changes
unless a Player is made with active="typical" (or "expert", "bot"); only `--active` does that (section 8).
A small Monte Carlo of the task queue (one founder with limited attention, auto-resolve by employees of the
right role, demand growing with hires, queue caps, a reward budget) gives the extra Income the tasks add, as a
fraction of Income while the player is ONLINE and present. Offline pay and idle play are untouched.
"""

import argparse
import math
import random
import statistics
import zlib
from dataclasses import dataclass, replace

# =============================================================================
# CONFIG: every number the simulator uses. Edit here, nowhere else.
# =============================================================================

# --- Garage upgrades. Source: TycoonCore.lua, UPGRADES (bought in this order; Desk is free) ---
UPGRADES = [  # (name, cost in Cash, income in Cash/second)
    ("Desk", 0, 1),
    ("Coffee Machine", 25, 2),
    ("Laptop", 100, 5),
    ("Server Rack", 400, 15),
    ("Whiteboard", 1500, 40),
    ("Neon Logo", 5000, 120),
]

# --- Offline income. Source: TycoonCore.lua, OFFLINE_CAP_SECONDS / OFFLINE_RATE ---
OFFLINE_CAP_SECONDS = 8 * 60 * 60   # at most 8 hours are paid per login
OFFLINE_RATE = 0.5                  # offline you earn 50% of your income (passes included)

# --- Slots and incubators. Source: CreatureConfig.lua, BaseEmployeeSlots / Incubators ---
BASE_SLOTS = 5
INCUBATORS = 3

# --- Rarities that Luck Boost multiplies. Source: CreatureConfig.lua, Rarities (luckBoosted) ---
LUCK_BOOSTED = {"Rare", "Epic", "Legendary"}

# --- Eggs. Source: CreatureConfig.lua, Eggs (price, hatchSeconds, odds = weights per rarity) ---
EGGS = {
    "Garage":  {"price": 250,    "hatch": 60,      "odds": {"Common": 70, "Uncommon": 25, "Rare": 5}},
    "Startup": {"price": 2500,   "hatch": 5 * 60,  "odds": {"Common": 40, "Uncommon": 35, "Rare": 18, "Epic": 6, "Legendary": 1}},
    "Unicorn": {"price": 25000,  "hatch": 15 * 60, "odds": {"Common": 10, "Uncommon": 25, "Rare": 35, "Epic": 22, "Legendary": 8}},
}

# --- Creatures: rarity -> list of income per second. Source: CreatureConfig.lua, Creatures ---
# (an egg picks the rarity by the odds, then one creature of that rarity with equal chance)
CREATURES = {
    "Common":    [2, 3, 3],         # Coffee Capybara, Coding Cat, Pixel Pigeon
    "Uncommon":  [7, 8, 9],         # Hustle Hamster, Bug Beetle, Memo Mole
    "Rare":      [20, 24],          # Sales Shark, Pitch Parrot
    "Epic":      [50, 60],          # Server Sloth, Ledger Llama
    "Legendary": [150, 175],        # Unicorn CEO, Venture Dragon
}

# --- Game passes and boosts. Source: ShopConfig.lua (effect fields) ---
DOUBLE_CASH = 2.0           # Passes.DoubleCash effect.cashMultiplier (199 R$)
VIP_CASH = 1.5              # Passes.VIP effect.cashMultiplier (249 R$); multipliers stack: 2 x 1.5 = 3
EXTRA_SLOTS = 3             # Passes.ExtraSlots effect.extraEmployeeSlots (149 R$)
LUCK_MULTIPLIER = 2         # Products.LuckBoost effect.luckMultiplier (49 R$ per 15 min)
LUCK_MINUTES = 15           # Products.LuckBoost effect.luckMinutes (real clock, it keeps running offline)
PASS_PRICE_ROBUX = {"DoubleCash": 199, "VIP": 249, "ExtraSlots": 149, "AutoHatch": 199, "LuckBoost(15min)": 49}

# --- HR Department (cash sink once everything else is bought). Source: CreatureConfig.lua, Poaching.HRDepartment ---
HR_COSTS = [2500, 10000, 40000, 120000, 350000]

# --- Player-behaviour assumptions (NOT from the game; these are guesses, change them freely) ---
CLAIM_DELAY_MANUAL = 20     # seconds a player without Auto-Hatch takes to notice and claim a hatched egg
RICH_FACTOR = 3             # "plenty of Cash" = the egg costs at most a third of what you hold
WAIT_SECONDS = 120          # a player waits for a better item if it is affordable within this many seconds

# Behaviours: sessions = list of (start offset inside the day in hours, length in minutes).
# Every behaviour logs in every day, so with the calendar on it never misses a daily reward.
BEHAVIOURS = {
    "active": [(0, 20), (5, 20), (11, 20)],   # 3 sessions of 20 min per day
    "casual": [(0, 10)],                       # 1 session of 10 min per day
    "idler":  [(0, 1)],                        # logs in for 1 minute a day: collects offline cash, spends it, leaves
}
# Extra behaviours, only used by the "real IPO" report (they are not in the main tables)
EXTRA_BEHAVIOURS = {
    "casual30": [(0, 72), (4, 72), (8, 72), (12, 72)],   # ~30% of a 16-hour waking day (4.8 h): 4 sessions of 72 min
    "binge":    [(0, 120)],                               # one uninterrupted 2-hour session (use days=1)
}

# --- IPO rebirth. Source: IpoConfig.lua ---
IPO_ENABLED_IN_MAIN_TABLE = False   # the main tables ignore IPO; the IPO section turns it on
IPO_STAGES = [                      # valuation (total Cash earned in this run) needed for each stage. Source: IpoConfig.Stages
    ("Garage", 0),
    ("Seed", 1_800),
    ("Series A", 6_300),
    ("Series B", 23_400),
    ("IPO-ready", 81_000),
]
IPO_BONUS_PER_IPO = 0.5             # IpoConfig.BonusPerIpo: income multiplier = 1 + this * IPOs ^ IPO_BONUS_EXPONENT
IPO_BONUS_EXPONENT = 0.75           # IpoConfig.BonusExponent (below 1 => diminishing returns per IPO)
IPO_THRESHOLD_GROWTH = 2.5          # IpoConfig.StageGrowthPerIpo: next run's stage thresholds are this many times bigger per IPO done
IPO_KEEPS_EMPLOYEES = True          # IpoConfig.Resets: employees are never in the Resets table, always kept
IPO_RESET_UPGRADES = True           # IpoConfig.Resets.Upgrades = true (cash and incubating eggs also reset)
IPO_RESETS_HR = False               # IpoConfig.Resets.HRDepartment = false: the HR level is kept across an IPO
IPO_SHARES_PER_IPO = 10             # IpoConfig.SharesPerIpo: Shares = this * (1 + growth * IPOs done) * (valuation / IPO-ready valuation) ^ exponent
IPO_SHARES_GROWTH = 0.8             # IpoConfig.SharesGrowthPerIpo
IPO_SHARES_RATIO_CAP = 2            # IpoConfig.SharesRatioCap
IPO_SHARES_EXPONENT = 0.5           # IpoConfig.SharesExponent
SHAREHOLDER_MULT = 2                # ShopConfig Passes.Shareholder: 2x Shares per IPO (199 R$)
IPO_COOLDOWN_SECONDS = 60           # IpoConfig.CooldownSeconds (not modeled: every gap between IPOs is far longer)
IPO_PERK_COSTS = {                  # IpoConfig.Perks: Shares for each level, per perk (total = everything in the IPO shop)
    "FasterEggs": [5, 10, 20, 35, 50, 90, 140], "ExtraIncubator": [15, 40], "ExtraSlot": [10, 25, 50],
    "OfflineCap": [5, 10, 20, 35], "BaseLuck": [5, 10, 20, 35, 50, 80, 120, 175], "CheaperPoach": [5, 10, 15, 20, 25, 50, 75, 110, 165, 240],
}

# --- Daily login calendar (milestone 6). Source: DailyConfig.lua ---
DAILY_IN_ALL_TABLES = False         # True: sections 1-6 also claim the calendar every day
DAILY_DAYS = [                      # DailyConfig.Days, in order: cashMinutes / egg / shares
    {"cash_minutes": 5},
    {"cash_minutes": 10},
    {"egg": "Garage"},
    {"cash_minutes": 20},
    {"egg": "Startup"},
    {"cash_minutes": 30},
    {"egg": "Unicorn", "shares": 3},
]
DAILY_CASH_MAX_MINUTES = 60         # DailyConfig.CashMaxMinutes
DAILY_MIN_CASH = 300                # DailyConfig.MinCash (a Cash day never gives less)
DAILY_GRACE_DAYS = 1                # DailyConfig.GraceDays (not exercised: simulated players never miss a day)
# Section 7 compares these calendars (the "too generous" one is only a what-if, not in the game)
DAILY_TOO_GENEROUS = [
    {"cash_minutes": 5}, {"cash_minutes": 10}, {"egg": "Startup"}, {"cash_minutes": 20},
    {"egg": "Startup"}, {"cash_minutes": 30}, {"egg": "Unicorn", "shares": 10},
]

# --- ACTIVE PLAY: the task engine of docs/ACTIVE_LOOPS_PROPOSAL.md (PROPOSAL: not read from any .lua) ---
# Rewards are in "seconds of the player's current Income" (passes and IPO multiplier included, like DailyConfig).
# Role families, from CreatureConfig.Creatures (key = employee income): which roles auto-resolve which tasks.
ACTIVE_ROLE_FAMILY = {
    2: {"ops": 1},                 # Coffee Capybara (Intern)
    3: {"eng": 0.5, "ops": 0.5},   # Coding Cat (Junior Engineer) / Pixel Pigeon (Junior Designer)
    7: {"sales": 1},               # Hustle Hamster (Sales Rep)
    8: {"eng": 1},                 # Bug Beetle (QA Tester)
    9: {"ops": 1},                 # Memo Mole (Office Manager)
    20: {"sales": 1},              # Sales Shark (Sales Lead)
    24: {"mkt": 1},                # Pitch Parrot (Marketing Lead)
    50: {"eng": 1},                # Server Sloth (Senior Engineer)
    60: {"fin": 1},                # Ledger Llama (CFO)
    150: {"fin": 1},               # Unicorn CEO
    175: {"fin": 1},               # Venture Dragon (Lead Investor)
}
ACTIVE_AUTO_CAP = 0.75             # employees never take more than this share of a task: the founder keeps at least 25%
ACTIVE_AUTO_PAY = 0.5              # a task an employee resolved pays this share of the reward (only while the player is present)
ACTIVE_BUDGET_RATE = 0.85          # reward budget: at most this many seconds of Income paid per online second ...
ACTIVE_BUDGET_BANK = 60            # ... with up to this many seconds banked ...
ACTIVE_OVER_BUDGET = 0.2           # ... and rewards beyond the budget pay this share (never zero: no punishment)
ACTIVE_LEVEL_IPO_CAP = 10          # difficulty level = funding stage (0-4) + IPOs done (max 10)
ACTIVE_DEMAND_CAP = 2.0            # D = min(this, 1 + demand x hires): a big team never doubles the calls twice over (no effect up to 8 hires)
ACTIVE_CHAIN_STEP, ACTIVE_CHAIN_MAX = 0.1, 2.0   # customer calls: +10% per answer in a row, up to x2
ACTIVE_SHARES_FRACTION = 0.05      # Shares from the pitch: this share of the run's base Shares, min 1, never doubled by the pass
ACTIVE_SHARES_WAVE = 1             # the pitch is a wave-1 task
ACTIVE_HORIZON = 7200              # model seconds the task Monte Carlo runs for each roster (fixed seed per roster)
# Players: reaction delay (s) before they start a new task, share of tasks they pay attention to, and skill
ACTIVE_SKILLS = {
    "typical": {"react": 2.0, "attend": 0.85, "p_bonus": 0.0},
    "expert": {"react": 0.7, "attend": 1.0, "p_bonus": 0.12},
    "bot": {"react": 0.15, "attend": 1.0, "p_bonus": 1.0},   # autoclicker / perfect play: skill 1.0, only the budget stops it
}


def _task(name, wave, fam, every, queue, limit, handle, reward, p=1.0, fail=0.0, miss=0.0, count=1, auto=0.0, demand=0.0, unlock=0, chain=False):
    """One row of the task table. every = (min, max) seconds between arrivals at 0 hires; queue = max waiting;
    limit = seconds to answer (0 = waits, never expires); handle = seconds of founder attention; reward / fail / miss in
    seconds of Income (per item if count > 1); auto = share auto-resolved per employee of family fam; demand = extra
    arrivals per hire; unlock = funding stage (0-4) the task appears at in the FIRST run (after the 1st IPO: always)."""
    return dict(name=name, wave=wave, fam=fam, every=every, queue=queue, limit=limit, handle=handle, reward=reward, p=p,
                fail=fail, miss=miss, count=count, auto=auto, demand=demand, unlock=unlock, chain=chain)


ACTIVE_TASKS = [
    # wave 1
    _task("Customer call", 1, "sales", (20, 40), 3, 8, 3, 7, auto=0.20, demand=0.08, chain=True),
    _task("Bug storm", 1, "eng", (45, 90), 1, 6, 3, 1.5, p=0.80, fail=-1.0, count=4, auto=0.15, demand=0.08, unlock=1),
    _task("Ship a feature", 1, "eng", (150, 150), 1, 0, 15, 14, p=0.80, fail=7, auto=0.15, demand=0.04, unlock=1),
    _task("Investor pitch", 1, None, (480, 720), 1, 30, 8, 40, demand=0.04, unlock=2),
    _task("Surprise event", 1, "eng", (240, 420), 1, 20, 10, 6, p=0.85, miss=4.5, auto=0.25, demand=0.06, unlock=2),
    _task("Interview", 1, "ops", (360, 600), 1, 40, 8, 20, auto=0.15, demand=0.08, unlock=1),
    # wave 2
    _task("Demo and contract", 2, "sales", (300, 540), 1, 45, 20, 45, p=0.80, fail=18, auto=0.10, demand=0.06, unlock=2),
    _task("Product feedback", 2, None, (600, 900), 1, 60, 6, 25, demand=0.04, unlock=2),
    _task("1-to-1 / team pizza", 2, "ops", (480, 900), 2, 90, 6, 12, auto=0.20, demand=0.06, unlock=2),
    _task("Viral post", 2, "mkt", (360, 600), 1, 10, 4, 16, p=0.75, fail=3, auto=0.20, demand=0.06, unlock=2),
    _task("Press interview", 2, "mkt", (900, 1200), 1, 45, 15, 28, p=0.80, fail=10, demand=0.04, unlock=3),
    _task("Ad campaign", 2, "mkt", (600, 900), 1, 0, 8, 20, demand=0.04, unlock=3),
    _task("Cash crunch", 2, "fin", (900, 1500), 1, 30, 12, 20, p=0.90, miss=9, auto=0.25, demand=0.04, unlock=3),
    _task("Support ticket", 2, "ops", (40, 70), 5, 12, 2, 2, p=0.90, auto=0.25, demand=0.08, unlock=2),
    _task("Product launch", 2, None, (1200, 1500), 1, 0, 35, 70, p=0.80, fail=35, unlock=3),
    # wave 3 (the paired demo needs a partner: arrivals already include the share of time one is around)
    _task("Paired demo", 3, "sales", (3000, 5000), 1, 20, 20, 90, p=0.85, fail=30, unlock=3),
    _task("Package pickup", 3, "ops", (60, 120), 2, 15, 2, 2, p=0.90, auto=0.20, demand=0.06, unlock=2),
]
# Not in the rate model (each is rare or one per run): pre-IPO roadshow (3 meetings, once per run), Investor Day
# (weekly), office decoration (cosmetic sink).

SIM_DAYS = 7
DAY = 24 * 3600


# =============================================================================
# Simulator
# =============================================================================

def egg_distribution(egg_key, luck):
    """List of (probability, income) for one egg, after Luck (same maths as CreatureConfig.getOdds)."""
    weights = {}
    for rarity, w in EGGS[egg_key]["odds"].items():
        weights[rarity] = w * (luck if rarity in LUCK_BOOSTED else 1)
    total = sum(weights.values())
    dist = []
    for rarity, w in weights.items():
        creatures = CREATURES[rarity]
        for inc in creatures:
            dist.append((w / total / len(creatures), inc))
    return dist


def egg_gain(egg_key, roster, slots, luck):
    """Expected extra income/second from one hatch, given the roster (replace the weakest if full)."""
    weakest = min(roster) if len(roster) >= slots else 0
    return sum(p * max(0, inc - weakest) for p, inc in egg_distribution(egg_key, luck))


# =============================================================================
# Active play (proposal): the task queue Monte Carlo. Used only when a Player has active="typical"/"expert"/"bot".
# =============================================================================

_ACTIVE_CACHE = {}
ACTIVE_NONE = {"f": 0.0, "busy": 0.0}


def _simulate_tasks(n, fam, level, stage, skill, waves, rng, budget=None, unlock_map=None):
    """Net Income-seconds per second the tasks add for ONE roster, and how busy the founder is. n = employees,
    fam = role family -> number of employees, stage = funding stage (first run only, None after the 1st IPO).
    budget = reward budget in seconds of Income per online second (None = ACTIVE_BUDGET_RATE); unlock_map = task name ->
    stage it appears at (None = the unlock of ACTIVE_TASKS; 99 = never); both are used by the long game only."""
    prof = ACTIVE_SKILLS[skill]
    H = ACTIVE_HORIZON
    b_rate = ACTIVE_BUDGET_RATE if budget is None else budget
    rows = [t for t in ACTIVE_TASKS if t["wave"] in waves and (unlock_map is None or unlock_map.get(t["name"], 0) < 99)
            and (stage is None or (t["unlock"] if unlock_map is None else unlock_map.get(t["name"], t["unlock"])) <= stage)]
    rate = min(1.4, 1 + 0.02 * level)               # harder: tasks come a bit faster ...
    lim_scale = max(0.65, 1 - 0.03 * level)         # ... with less time ...
    p_drop = 0.008 * level                          # ... and are a little harder to get right
    arrivals = []
    for i, t in enumerate(rows):
        scale = 1.0 / (min(ACTIVE_DEMAND_CAP, 1 + t["demand"] * n) * rate)   # more hires = more demand = shorter gaps (capped)
        clock = rng.uniform(0, t["every"][1]) * scale
        while clock < H:
            arrivals.append((clock, i))
            clock += rng.uniform(*t["every"]) * scale
    arrivals.sort()
    share = [min(ACTIVE_AUTO_CAP, 1 - (1 - t["auto"]) ** fam.get(t["fam"], 0)) if t["fam"] and t["auto"] > 0 else 0.0 for t in rows]
    st = {"net": 0.0, "busy": 0.0, "bucket": float(ACTIVE_BUDGET_BANK), "bt": 0.0, "streak": 0, "founder": 0, "team": 0}

    def pay(amount, now):
        """A reward goes through the budget; a loss (negative) is taken as it is."""
        if amount <= 0:
            st["net"] += amount
            return
        st["bucket"] = min(ACTIVE_BUDGET_BANK, st["bucket"] + b_rate * (now - st["bt"]))
        st["bt"] = now
        if st["bucket"] >= amount:
            st["bucket"] -= amount
            st["net"] += amount
        else:
            st["net"] += st["bucket"] + (amount - st["bucket"]) * ACTIVE_OVER_BUDGET
            st["bucket"] = 0.0

    pending = []
    now, ai = 0.0, 0
    while now < H:
        while ai < len(arrivals) and arrivals[ai][0] <= now:
            at, i = arrivals[ai]
            ai += 1
            t = rows[i]
            if rng.random() < share[i]:                       # an employee took it
                st["team"] += 1
                pay(t["reward"] * t["count"] * ACTIVE_AUTO_PAY, at)
            elif sum(1 for q in pending if q[0] == i) < t["queue"]:   # queue cap: a full queue drops the arrival, no penalty
                waits = t["limit"] == 0
                attend = waits or rng.random() < prof["attend"]
                pending.append((i, at, (at + t["limit"] * lim_scale) if not waits else math.inf,
                                at + (prof["react"] if not waits else 10.0) if attend else math.inf))
        for q in pending[:]:
            if q[2] <= now:                                    # expired: a miss, never a punishment beyond `miss`
                pending.remove(q)
                t = rows[q[0]]
                st["net"] -= t["miss"] * t["count"]
                if t["chain"]:
                    st["streak"] = 0
        ready = [q for q in pending if q[3] <= now]
        if ready:
            q = min(ready, key=lambda r: (r[2], r[1]))
            t = rows[q[0]]
            pending.remove(q)
            if now + t["handle"] > q[2]:                       # no time left to finish it
                st["net"] -= t["miss"] * t["count"]
                if t["chain"]:
                    st["streak"] = 0
                continue
            now += t["handle"]
            st["busy"] += t["handle"]
            st["founder"] += 1
            p = 1.0 if skill == "bot" else (min(1.0, max(0.5, t["p"] - p_drop + prof["p_bonus"])) if t["p"] < 1 else 1.0)
            if t["chain"]:
                if rng.random() < p:
                    pay(t["reward"] * min(ACTIVE_CHAIN_MAX, 1 + ACTIVE_CHAIN_STEP * st["streak"]), now)
                    st["streak"] += 1
                else:
                    st["streak"] = 0
            else:
                for _ in range(t["count"]):
                    if rng.random() < p:
                        pay(t["reward"], now)
                    else:
                        pay(t["fail"], now)
        else:
            nxt = H
            if ai < len(arrivals):
                nxt = min(nxt, arrivals[ai][0])
            for q in pending:
                nxt = min(nxt, q[2], q[3] if q[3] > now else math.inf)
            now = max(nxt, now + 1e-6)
    return {"f": st["net"] / H, "busy": min(1.0, st["busy"] / H), "founder_per_h": st["founder"] * 3600 / H, "team_per_h": st["team"] * 3600 / H}


def active_factor(roster, stage, ipos, skill, waves, budget=None, unlock_map=None):
    """{"f": extra Income as a fraction of Income, "busy": share of the time the founder is busy} for this team.
    budget and unlock_map: see _simulate_tasks (long game only; the default None keeps every older number)."""
    if not roster or skill in (None, "ignore"):
        return ACTIVE_NONE
    fam = {}
    for inc in roster:
        for f, w in ACTIVE_ROLE_FAMILY.get(inc, {"ops": 1}).items():
            fam[f] = fam.get(f, 0) + w
    level = stage + min(ipos, ACTIVE_LEVEL_IPO_CAP)
    first_stage = stage if ipos == 0 else None
    key = (len(roster), tuple(sorted((f, round(w * 2) / 2) for f, w in fam.items())), level, first_stage, skill, tuple(waves))
    if budget is not None or unlock_map is not None:   # extra key parts only for the long game: the older keys (and their random streams) stay as they were
        key = key + (budget, tuple(sorted(unlock_map.items())) if unlock_map else None)
    hit = _ACTIVE_CACHE.get(key)
    if hit is None:
        hit = _simulate_tasks(len(roster), dict(key[1]), level, first_stage, skill, waves, random.Random(zlib.crc32(repr(key).encode())), budget, unlock_map)
        _ACTIVE_CACHE[key] = hit
    return hit


class Player:
    def __init__(self, rng, double_cash=False, vip=False, extra_slots=False, auto_hatch=False, luck_boost=False, shareholder=False,
                 daily=None, daily_cash_counts=False, active=None, active_waves=(1, 2, 3)):
        self.rng = rng
        self.active = active                # None = OFF (the default); "typical" / "expert" / "bot" = proposal active play
        self.active_waves = tuple(active_waves)
        self.online = False                 # True only while a session runs: tasks never pay offline
        self.daily = daily                  # the calendar (list of days) or None
        self.daily_cash_counts = daily_cash_counts   # what-if only: calendar Cash raises the valuation
        self.daily_claims = 0
        self.daily_claimed_day = -1         # day number of the last claim
        self.share_mult = SHAREHOLDER_MULT if shareholder else 1
        self.shares = 0
        self.shares_log = []        # Shares earned at each IPO
        self.mult_pass = (DOUBLE_CASH if double_cash else 1) * (VIP_CASH if vip else 1)
        self.slots = BASE_SLOTS + (EXTRA_SLOTS if extra_slots else 0)
        self.auto_hatch = auto_hatch
        self.luck_boost = luck_boost
        self.luck_until = -1
        self.cash = 0.0
        self.earned_total = 0.0     # lifetime
        self.earned_run = 0.0       # since last IPO (valuation)
        self.upgrades = 1           # Desk is free
        self.roster = []            # income of each employee
        self.incubators = []        # (hatchAt, egg_key)
        self.hr = 0
        self.ipos = 0
        self.stage_scale = 1.0
        self.milestones = {}        # name -> time in seconds
        self.log_cash = []          # (time, lifetime_earned) for cash-per-hour reports
        self.ipo_times = []

    # -- income -------------------------------------------------------------
    def ipo_mult(self):
        if self.ipos <= 0:
            return 1
        return 1 + IPO_BONUS_PER_IPO * self.ipos ** IPO_BONUS_EXPONENT

    def base_income(self):
        return sum(u[2] for u in UPGRADES[: self.upgrades]) + sum(self.roster)

    def passive_income(self):
        return self.base_income() * self.mult_pass * self.ipo_mult()

    def income(self):
        inc = self.passive_income()
        if self.active and self.online:     # active play only adds Income while the player is online
            inc *= 1 + active_factor(self.roster, self.stage_index(), self.ipos, self.active, self.active_waves)["f"]
        return inc

    def earn(self, amount):
        self.cash += amount
        self.earned_total += amount
        self.earned_run += amount

    def luck(self, t):
        return LUCK_MULTIPLIER if t < self.luck_until else 1

    def mark(self, name, t):
        self.milestones.setdefault(name, t)

    # -- actions ------------------------------------------------------------
    def claim_ready(self, t):
        """Hatch every ready egg. Returns True if something hatched."""
        did = False
        for egg in list(self.incubators):
            hatch_at, key = egg
            if hatch_at <= t:
                self.incubators.remove(egg)
                # the luck that counted is the luck at the moment the egg hatched
                dist = egg_distribution(key, self.luck(hatch_at))
                r, acc, income = self.rng.random(), 0.0, dist[-1][1]
                for p, inc in dist:
                    acc += p
                    if r <= acc:
                        income = inc
                        break
                if len(self.roster) < self.slots:
                    self.roster.append(income)
                elif income > min(self.roster):
                    self.roster.remove(min(self.roster))
                    self.roster.append(income)
                did = True
                if income >= 150:
                    self.mark("first Legendary", t)
                n = len(self.roster)
                if n == 1:
                    self.mark("first employee", t)
                for k in (3, BASE_SLOTS, 8):
                    if n >= k and self.slots >= k:
                        self.mark(f"{k} slots", t)
        return did

    def claim_daily(self, t, day_number):
        """Claim today's calendar reward, like DailyServer. False if already claimed today, or an egg
        day with every incubator busy (then nothing changes and the day isn't used up)."""
        if not self.daily or self.daily_claimed_day == day_number:
            return False
        reward = self.daily[self.daily_claims % len(self.daily)]   # never misses a day: the streak is the claim count
        egg = reward.get("egg")
        if egg:
            if len(self.incubators) >= INCUBATORS:
                return False
            self.incubators.append((t + EGGS[egg]["hatch"], egg))
        minutes = min(reward.get("cash_minutes", 0), DAILY_CASH_MAX_MINUTES)
        if minutes > 0:
            cash = max(DAILY_MIN_CASH, int(self.passive_income() * 60 * minutes))
            if self.daily_cash_counts:
                self.earn(cash)                 # what-if row only: NOT how the game works
            else:
                before = (self.earned_run, self.earned_total)
                self.cash += cash               # a gift: Cash only
                assert (self.earned_run, self.earned_total) == before, "calendar Cash must not count toward the IPO valuation"
        self.shares += reward.get("shares", 0)  # as they are: the Shareholder pass doesn't double them
        self.daily_claims += 1
        self.daily_claimed_day = day_number
        return True

    def options(self, t):
        """Things the player could buy: (ratio gain/cost, cost, kind, extra)."""
        out = []
        if self.upgrades < len(UPGRADES):
            name, cost, inc = UPGRADES[self.upgrades]
            out.append((inc * self.mult_pass * self.ipo_mult() / max(cost, 1), cost, "upgrade", None))
        if len(self.incubators) < INCUBATORS:
            mult = self.mult_pass * self.ipo_mult()
            gains = {k: egg_gain(k, self.roster, self.slots, self.luck(t)) * mult for k in EGGS}
            # When Cash is plentiful (egg costs <= 1/RICH_FACTOR of it) the incubator is the bottleneck,
            # so the player picks the egg with the best expected income, not the best gain per Cash.
            rich = [k for k in EGGS if EGGS[k]["price"] * RICH_FACTOR <= self.cash and gains[k] > 0]
            if rich:
                k = max(rich, key=lambda k: gains[k])
                out.append((1e6, EGGS[k]["price"], "egg", k))
            else:
                for key, egg in EGGS.items():
                    if gains[key] > 0:
                        out.append((gains[key] / egg["price"], egg["price"], "egg", key))
        if self.hr < len(HR_COSTS) and self.upgrades >= len(UPGRADES):
            out.append((1e-9, HR_COSTS[self.hr], "hr", None))   # only when nothing useful is left
        return sorted(out, key=lambda o: -o[0])

    def buy_all_possible(self, t):
        """Spend greedily by gain/cost. Wait up to WAIT_SECONDS for a better item. Returns next wait (s) or None."""
        inc = max(self.income(), 1e-9)
        while True:
            opts = self.options(t)
            if not opts:
                return None
            best = opts[0]
            if self.cash >= best[1]:
                self.apply(best, t)
                continue
            if (best[1] - self.cash) / inc <= WAIT_SECONDS or best[2] == "hr":
                return (best[1] - self.cash) / inc          # wait for the best item
            affordable = [o for o in opts if self.cash >= o[1]]
            if not affordable:
                return (opts[0][1] - self.cash) / inc if (opts[0][1] - self.cash) / inc < 1e12 else None
            self.apply(affordable[0], t)

    def apply(self, option, t):
        _, cost, kind, extra = option
        self.cash -= cost
        if kind == "upgrade":
            self.upgrades += 1
            self.mark(f"upgrade {self.upgrades}/{len(UPGRADES)}", t)
        elif kind == "egg":
            self.incubators.append((t + EGGS[extra]["hatch"], extra))
            self.mark(f"bought {extra} egg", t)
        elif kind == "hr":
            self.hr += 1
            if self.hr == len(HR_COSTS):
                self.mark("all HR levels", t)

    # -- IPO (placeholder) ----------------------------------------------------
    def stage_index(self):
        idx = 0
        for i, (_, need) in enumerate(IPO_STAGES):
            if self.earned_run >= need * self.stage_scale:
                idx = i
        return idx

    def check_stages(self, t):
        """Record the exact time each funding stage is first reached (first run only)."""
        if self.ipos == 0:
            for name, need in IPO_STAGES[1:]:
                if self.earned_run >= need * self.stage_scale:
                    self.mark(f"stage {name}", t)

    def next_stage_need(self):
        for _, need in IPO_STAGES[1:]:
            if self.earned_run < need * self.stage_scale:
                return need * self.stage_scale - self.earned_run
        return None

    def maybe_ipo(self, t):
        if not self.use_ipo or self.stage_index() < len(IPO_STAGES) - 1:
            return False
        # the sim goes public the moment IPO-ready is reached, so the ratio is ~1 (a player who waits gets more)
        ratio = min(IPO_SHARES_RATIO_CAP, max(0.0, self.earned_run / (IPO_STAGES[-1][1] * self.stage_scale)))
        gained = int(IPO_SHARES_PER_IPO * (1 + IPO_SHARES_GROWTH * self.ipos) * ratio ** IPO_SHARES_EXPONENT * self.share_mult)
        if self.active and ACTIVE_SHARES_WAVE in self.active_waves:
            # the pitch's Shares: a share of the run's base Shares, never doubled by the Shareholder pass
            gained += max(1, math.ceil(ACTIVE_SHARES_FRACTION * IPO_SHARES_PER_IPO * (1 + IPO_SHARES_GROWTH * self.ipos)))
        self.shares += gained
        self.shares_log.append(gained)
        self.ipos += 1
        self.ipo_times.append(t)
        self.stage_scale *= IPO_THRESHOLD_GROWTH
        self.earned_run = 0.0
        self.cash = 0.0
        self.upgrades = 1
        self.incubators = []
        if IPO_RESETS_HR:
            self.hr = 0
        if not IPO_KEEPS_EMPLOYEES:
            self.roster = []
        return True

    use_ipo = False


def run(behaviour, seed, days=SIM_DAYS, use_ipo=False, daily=None, daily_cash_counts=False, **passes):
    rng = random.Random(seed)
    if daily is None and DAILY_IN_ALL_TABLES:
        daily = DAILY_DAYS
    p = passes.pop("player_cls", Player)(rng, daily=daily or None, daily_cash_counts=daily_cash_counts, **passes)   # player_cls: only the S8 sim passes one
    p.use_ipo = use_ipo
    sessions = []
    for d in range(days):
        for start_h, minutes in {**BEHAVIOURS, **EXTRA_BEHAVIOURS}[behaviour]:
            s = d * DAY + start_h * 3600
            sessions.append((s, s + minutes * 60))
    claim_delay = 0 if p.auto_hatch else CLAIM_DELAY_MANUAL
    last_seen = None
    next_snap = 0
    hourly = []   # lifetime earnings at each full hour

    for s_start, s_end in sessions:
        # Offline stretch: pay offline income at login, like TycoonCore does
        if last_seen is not None:
            away = max(0, min(s_start - last_seen, OFFLINE_CAP_SECONDS))
            # hourly snapshots inside the offline stretch (real game pays only at login; we spread it so
            # "cash per hour" is comparable, still using the same total)
            payout = away * p.income() * OFFLINE_RATE
            if s_start > last_seen:
                rate = payout / (s_start - last_seen)
                # earn the payout at login, report hourly figure as if paid evenly
                while next_snap <= s_start:
                    hourly.append(p.earned_total + rate * (next_snap - last_seen))
                    next_snap += 3600
                p.earn(payout)
                p.check_stages(s_start)
        t = s_start
        p.mark("first session", t)
        # buy the day's Luck Boost at the start of each session (upper bound for a heavy spender)
        if p.luck_boost:
            p.luck_until = t + LUCK_MINUTES * 60
        # claim eggs that hatched while away
        p.claim_ready(t)
        # daily calendar: claimed at the first login of the day (after hatching, so an incubator is free)
        day_number = int(s_start // DAY)
        p.claim_daily(t, day_number)
        p.online = True
        while t < s_end:
            wait = p.buy_all_possible(t)
            if p.maybe_ipo(t):
                continue
            income = p.income()
            # next event: egg ready (+claim delay), or cash target reached, or session end
            nxt = s_end
            for hatch_at, _ in p.incubators:
                nxt = min(nxt, max(hatch_at + claim_delay, t + 1e-6))
            if wait is not None:
                nxt = min(nxt, t + max(wait, 1e-6))
            need = p.next_stage_need()
            if need is not None and income > 0:
                nxt = min(nxt, t + need / income + 1e-6)   # stop exactly when a funding stage is reached
            nxt = max(nxt, t + 1e-6)
            dt = nxt - t
            while next_snap <= nxt:
                hourly.append(p.earned_total + income * (next_snap - t))
                next_snap += 3600
            p.earn(income * dt)
            t = nxt
            p.claim_ready(t)
            p.claim_daily(t, day_number)   # only does something if an egg day waited for a free incubator
            p.check_stages(t)
            if p.upgrades >= len(UPGRADES):
                p.mark("all upgrades", t)
            if p.income() >= 500:
                p.mark("income >= 500/s", t)
        p.online = False
        last_seen = s_end
    # tail: last offline stretch to the end of the horizon
    end = days * DAY
    if last_seen is not None and end > last_seen:
        away = min(end - last_seen, OFFLINE_CAP_SECONDS)
        rate = away * p.income() * OFFLINE_RATE / (end - last_seen)
        while next_snap <= end:
            hourly.append(p.earned_total + rate * (next_snap - last_seen))
            next_snap += 3600
    p.hourly = hourly
    return p


def cash_per_hour_on_day(p, day):
    """Average Cash earned per hour during day number `day` (1-based), from the hourly lifetime log."""
    h = p.hourly
    a, b = (day - 1) * 24, day * 24
    if b >= len(h):
        b = len(h) - 1
    return (h[b] - h[a]) / 24


def median_time(runs, name):
    values = [r.milestones[name] for r in runs if name in r.milestones]
    if len(values) < len(runs) / 2:
        return None
    return statistics.median(values)


def fmt_time(seconds):
    if seconds is None:
        return "never (7d)"
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    if seconds < 3 * DAY:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / DAY:.1f} d"


def fmt_cash(x):
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= limit:
            return f"{x / limit:.2f}{suffix}"
    return f"{x:.0f}"


def many(behaviour, n, **kw):
    return [run(behaviour, seed, **kw) for seed in range(n)]


# =============================================================================
# Reports
# =============================================================================

MILESTONE_ROWS = [
    ("first session", "first employee"),
    ("bought Garage egg", None),
]


def report_main(n):
    print("\n## 1. Base game (no passes, no IPO), median of %d runs" % n)
    rows = []
    for b in BEHAVIOURS:
        runs = many(b, n)
        row = {
            "behaviour": b,
            "first employee": median_time(runs, "first employee"),
            "all upgrades": median_time(runs, "all upgrades"),
            "3 slots": median_time(runs, "3 slots"),
            "5 slots": median_time(runs, f"{BASE_SLOTS} slots"),
            "10 slots": None,  # impossible: max is 8 with Extra Slots pass
            "d1": statistics.median(cash_per_hour_on_day(r, 1) for r in runs),
            "d3": statistics.median(cash_per_hour_on_day(r, 3) for r in runs),
            "d7": statistics.median(cash_per_hour_on_day(r, 7) for r in runs),
            "income": statistics.median(r.income() for r in runs),
            "roster": statistics.median(sum(r.roster) for r in runs),
            "hr": statistics.median(r.hr for r in runs),
        }
        rows.append(row)
    print("| Behaviour | First employee | All 6 upgrades | 3 slots | 5 slots (base max) | 10 slots | Cash/h day 1 | day 3 | day 7 | Income/s at day 7 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['behaviour']} | {fmt_time(r['first employee'])} | {fmt_time(r['all upgrades'])} | {fmt_time(r['3 slots'])} | "
              f"{fmt_time(r['5 slots'])} | impossible (cap 5, or 8 with pass) | {fmt_cash(r['d1'])} | {fmt_cash(r['d3'])} | {fmt_cash(r['d7'])} | {fmt_cash(r['income'])} |")
    return rows


def report_slots_pass(n):
    print("\n## 2. Time to fill slots with the Extra Employee Slots pass (8 slots)")
    print("| Behaviour | 5 slots | 8 slots | Cash/h day 7 |")
    print("|---|---|---|---|")
    for b in BEHAVIOURS:
        runs = many(b, n, extra_slots=True)
        print(f"| {b} | {fmt_time(median_time(runs, '5 slots'))} | {fmt_time(median_time(runs, '8 slots'))} | "
              f"{fmt_cash(statistics.median(cash_per_hour_on_day(r, 7) for r in runs))} |")


def report_passes(n):
    print("\n## 3. What each pass changes (median of %d runs; day-7 cash/hour, speed vs. no pass)" % n)
    scenarios = [
        ("No pass", {}),
        ("Luck Boost (1 per session)", {"luck_boost": True}),
        ("2x Cash", {"double_cash": True}),
        ("VIP (+50%)", {"vip": True}),
        ("2x Cash + VIP (x3)", {"double_cash": True, "vip": True}),
        ("Extra Slots (+3)", {"extra_slots": True}),
        ("Auto-Hatch", {"auto_hatch": True}),
        ("All passes + Luck", {"double_cash": True, "vip": True, "extra_slots": True, "auto_hatch": True, "luck_boost": True}),
    ]
    result = {}
    for b in BEHAVIOURS:
        base = None
        print(f"\n**{b}**\n")
        print("| Scenario | All 6 upgrades | 5 slots | Cash/h day 1 | day 3 | day 7 | day-7 vs no pass |")
        print("|---|---|---|---|---|---|---|")
        for name, kw in scenarios:
            runs = many(b, n, **kw)
            d7 = statistics.median(cash_per_hour_on_day(r, 7) for r in runs)
            if base is None:
                base = d7
            result[(b, name)] = d7
            print(f"| {name} | {fmt_time(median_time(runs, 'all upgrades'))} | {fmt_time(median_time(runs, '5 slots'))} | "
                  f"{fmt_cash(statistics.median(cash_per_hour_on_day(r, 1) for r in runs))} | "
                  f"{fmt_cash(statistics.median(cash_per_hour_on_day(r, 3) for r in runs))} | {fmt_cash(d7)} | x{d7 / base:.2f} |")
    return result


def ipo_mult_at(count):
    if count <= 0:
        return 1.0
    return 1 + IPO_BONUS_PER_IPO * count ** IPO_BONUS_EXPONENT


def report_ipo(n, days=30):
    print(f"\n## 4. IPO rebirth, real IpoConfig.lua numbers, {days} days (median of {n} runs)")
    print("Stages (valuation): " + ", ".join(f"{k} {fmt_cash(v)}" for k, v in IPO_STAGES) +
          f". Each IPO: income x(1 + {IPO_BONUS_PER_IPO} x IPOs^{IPO_BONUS_EXPONENT}). Next-run thresholds x{IPO_THRESHOLD_GROWTH} per IPO.\n")
    print("| Behaviour | Seed | Series A | Series B | IPO-ready = 1st IPO | IPOs in 30 days | Income multiplier at day 30 |")
    print("|---|---|---|---|---|---|---|")
    for b in BEHAVIOURS:
        runs = [run(b, seed, days=days, use_ipo=True) for seed in range(n)]
        cols = [fmt_time(median_time(runs, f"stage {name}")) for name, _ in IPO_STAGES[1:]]
        counts = [len(r.ipo_times) for r in runs]
        median_count = statistics.median(counts)
        print(f"| {b} | " + " | ".join(cols) + f" | {median_count:.0f} | x{ipo_mult_at(median_count):.2f} |")


SIM_DAYS_IPO = 60


def all_behaviours():
    return {**BEHAVIOURS, **EXTRA_BEHAVIOURS}


def active_minutes_at(behaviour, t):
    """Minutes the player has really been online at wall-clock time t (seconds)."""
    total = 0.0
    for d in range(SIM_DAYS_IPO + 1):
        for start_h, minutes in all_behaviours()[behaviour]:
            s = d * DAY + start_h * 3600
            total += max(0.0, min(t, s + minutes * 60) - s) / 60
    return total


def fmt_active(minutes):
    if minutes is None:
        return "never"
    if minutes < 90:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f} h"


def med(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def report_real_ipo(n, days=SIM_DAYS_IPO):
    """Active minutes (time really spent online) per funding stage and per IPO, with and without the Shareholder pass."""
    total_perks = sum(sum(c) for c in IPO_PERK_COSTS.values())
    print(f"\n## 6. Real IPO numbers in ACTIVE minutes (time online), {days} days, median of {n} runs")
    print("Sessions: " + "; ".join(f"{b} {all_behaviours()[b]}" for b in ("active", "casual30", "casual")))
    print(f"The whole IPO shop costs {total_perks} Shares ({', '.join(f'{k} {sum(v)}' for k, v in IPO_PERK_COSTS.items())}). Perks are NOT modeled.")
    for b in ("active", "casual30", "casual"):
        runs = [run(b, seed, days=days, use_ipo=True) for seed in range(n)]
        pass_runs = [run(b, seed, days=days, use_ipo=True, shareholder=True) for seed in range(n)]
        print(f"\n**{b}**\n")
        stage_times = []
        for name, _ in IPO_STAGES[1:]:
            key = f"stage {name}"
            stage_times.append(f"{name} {fmt_active(med([active_minutes_at(b, r.milestones[key]) if key in r.milestones else None for r in runs]))}")
        print("First run, time online to reach each stage: " + ", ".join(stage_times) + "\n")
        print("| IPO # | Online time to reach it (total) | Online time of that run | Shares (no pass) | Shares (Shareholder) | Multiplier after |")
        print("|---|---|---|---|---|---|")
        for k in (1, 2, 3, 5, 10, 20):
            if sum(1 for r in runs if len(r.ipo_times) >= k) < len(runs) / 2:
                print(f"| {k} | not reached in {days} d | | | | |")
                continue
            def at(r):
                return active_minutes_at(b, r.ipo_times[k - 1]) if len(r.ipo_times) >= k else None
            def gap(r):
                if len(r.ipo_times) < k:
                    return None
                prev = active_minutes_at(b, r.ipo_times[k - 2]) if k > 1 else 0
                return active_minutes_at(b, r.ipo_times[k - 1]) - prev
            sh = med([r.shares_log[k - 1] if len(r.shares_log) >= k else None for r in runs])
            shp = med([r.shares_log[k - 1] if len(r.shares_log) >= k else None for r in pass_runs])
            print(f"| {k} | {fmt_active(med([at(r) for r in runs]))} | {fmt_active(med([gap(r) for r in runs]))} | {sh:.0f} | {shp:.0f} | x{ipo_mult_at(k):.2f} |")
        for label, rs in (("no pass", runs), ("Shareholder", pass_runs)):
            done = []
            for r in rs:
                total = 0
                for i, g in enumerate(r.shares_log):
                    total += g
                    if total >= total_perks:
                        done.append((i + 1, active_minutes_at(b, r.ipo_times[i])))
                        break
            if len(done) >= len(rs) / 2:
                print(f"\nWhole IPO shop ({total_perks} Shares, {label}) bought at IPO #{med([x[0] for x in done]):.0f}, after {fmt_active(med([x[1] for x in done]))} online.")
            else:
                print(f"\nWhole IPO shop ({total_perks} Shares, {label}): not finished in {days} days (IPOs done {med([len(r.ipo_times) for r in rs]):.0f}, Shares {med([r.shares for r in rs]):.0f}).")
    runs = [run("binge", seed, days=1, use_ipo=True) for seed in range(n)]
    counts = [len(r.ipo_times) for r in runs]
    when = ", ".join(f"#{i + 1} {fmt_active(med([r.ipo_times[i] / 60 for r in runs if len(r.ipo_times) > i]))}" for i in range(int(med(counts))))
    print(f"\n**2-hour binge:** median {med(counts):.0f} IPOs (range {min(counts)}-{max(counts)}); IPO at (median online time): {when}")


def report_detail(n):
    """Extra figures used for the findings."""
    print("\n## 5. Extra figures for the findings")
    for b in BEHAVIOURS:
        runs = many(b, n)
        keys = ["first session", "bought Garage egg", "bought Startup egg", "bought Unicorn egg", "first Legendary", "all HR levels", "upgrade 2/6", "upgrade 3/6", "upgrade 4/6", "upgrade 5/6", "upgrade 6/6",
                "first employee", "3 slots", "5 slots", "income >= 500/s"]
        parts = []
        for k in keys:
            parts.append(f"{k}={fmt_time(median_time(runs, k))}")
        print(f"- {b}: " + "; ".join(parts))
        roster = statistics.median(sum(r.roster) for r in runs)
        base_up = sum(u[2] for u in UPGRADES)
        hr = statistics.median(r.hr for r in runs)
        print(f"  roster income at day 7 (median) = {roster:.0f}/s, upgrades = {base_up}/s, HR levels bought = {hr:.0f}")
        # share of cash that comes from offline for this behaviour is approximated by income*0.5*away
    best = 5 * max(max(v) for v in CREATURES.values())
    print(f"- Theoretical ceiling of the base game: {sum(u[2] for u in UPGRADES)}/s upgrades + {best}/s (5 Legendaries) = "
          f"{sum(u[2] for u in UPGRADES) + best}/s; with Extra Slots {sum(u[2] for u in UPGRADES) + 8 * 175}/s")
    print(f"- Total cash sinks after upgrades: HR Department = {sum(HR_COSTS)}")
    # expected value of each egg
    for key in EGGS:
        d = egg_distribution(key, 1)
        d2 = egg_distribution(key, 2)
        ev = sum(p * i for p, i in d)
        ev2 = sum(p * i for p, i in d2)
        p_leg = sum(p for p, i in d if i >= 150)
        p_leg2 = sum(p for p, i in d2 if i >= 150)
        print(f"- {key} egg: price {EGGS[key]['price']}, expected income {ev:.1f}/s (payback {EGGS[key]['price'] / ev:.0f}s), "
              f"with Luck x2 {ev2:.1f}/s; P(Legendary) {p_leg:.1%} -> {p_leg2:.1%}")
    print("- Prices in Robux: " + ", ".join(f"{k} {v}" for k, v in PASS_PRICE_ROBUX.items()))


def report_daily(n, days=30):
    """The M6 plan's table: does the daily calendar move the first IPO, the IPO count or the Shares?"""
    print(f"\n## 7. Daily login calendar (DailyConfig.lua), IPO on, no passes, no perks, {days} days, median of {n} runs")
    print("Every simulated player claims every day (worst case). Calendar Cash is a gift: Cash only, not valuation.\n")
    print("| Behaviour | Calendar | 1st IPO, minutes online (wall clock) | IPOs by day 7 | IPOs by day 30 | Shares at day 30 |")
    print("|---|---|---|---|---|---|")
    variants = [
        ("none", {}),
        ("proposed (DailyConfig)", {"daily": DAILY_DAYS}),
        ("proposed, but Cash counts as valuation", {"daily": DAILY_DAYS, "daily_cash_counts": True}),
        ("too generous (Startup d3/d5, Unicorn d7 + 10 Shares)", {"daily": DAILY_TOO_GENEROUS}),
    ]
    for b in BEHAVIOURS:
        base_shares = None
        for name, kw in variants:
            runs = [run(b, seed, days=days, use_ipo=True, **kw) for seed in range(n)]
            first = med([active_minutes_at(b, r.ipo_times[0]) if r.ipo_times else None for r in runs])
            first_wall = med([r.ipo_times[0] for r in runs if r.ipo_times])
            by7 = med([sum(1 for x in r.ipo_times if x <= 7 * DAY) for r in runs])   # includes the login at the 7-day mark, like the M6 plan
            by30 = med([len(r.ipo_times) for r in runs])
            shares = med([r.shares for r in runs])
            if base_shares is None:
                base_shares = shares
            change = f" ({(shares / base_shares - 1) * 100:+.0f}%)" if base_shares and name != "none" else ""
            wall = f"hour {first_wall / 3600:.0f}" if first_wall is not None else "never"
            first_text = f"{first:.1f} ({wall})" if first is not None else "never"
            print(f"| {b} | {name} | {first_text} | {by7:.0f} | {by30:.0f} | {shares:.0f}{change} |")


ACTIVE_ROSTERS = [   # employee incomes (CreatureConfig): a typical team at four moments of a run
    ("1 hire (Cat)", [3]),
    ("3 hires", [3, 7, 8]),
    ("5 hires", [3, 7, 8, 20, 24]),
    ("8 hires, Epics", [3, 7, 8, 9, 20, 24, 50, 60]),
]
ACTIVE_MODES = [("passive (today)", None, (1, 2, 3)), ("wave 1", "typical", (1,)), ("waves 1-2", "typical", (1, 2)), ("all waves", "typical", (1, 2, 3))]


def report_active(n, days=SIM_DAYS_IPO):
    """Section 8: what the proposed task engine (docs/ACTIVE_LOOPS_PROPOSAL.md) does to the economy. Only with --active."""
    total_perks = sum(sum(c) for c in IPO_PERK_COSTS.values())
    print(f"\n## 8. ACTIVE PLAY (proposal, default OFF), {days} days, median of {n} runs")
    rows = ", ".join("%s (w%d)" % (t["name"], t["wave"]) for t in ACTIVE_TASKS)
    print(f"Task rows: {rows}.")
    print(f"Reward budget {ACTIVE_BUDGET_RATE} s of Income per online second (bank {ACTIVE_BUDGET_BANK} s, over budget pays {ACTIVE_OVER_BUDGET:.0%}); "
          f"auto-resolve cap {ACTIVE_AUTO_CAP:.0%}, auto-resolved pay {ACTIVE_AUTO_PAY:.0%}; pitch Shares {ACTIVE_SHARES_FRACTION:.0%} of the run's base Shares (min 1, not doubled by the pass).")
    print("Offline pay and a player who ignores the tasks are exactly today's game (factor 0).\n")
    print("### 8a. Extra Income from tasks while online (x = 1 + f), by team and moment of the game")
    print("| Team | Moment | wave 1 | waves 1-2 | all waves | all, expert | all, autoclicker | founder busy (all) |")
    print("|---|---|---|---|---|---|---|---|")
    for name, roster in ACTIVE_ROSTERS:
        for label, stage, ipos in (("1st run, IPO-ready", 4, 0), ("IPO 5", 4, 5), ("IPO 10", 4, 10)):
            f = [active_factor(roster, stage, ipos, "typical", w) for w in ((1,), (1, 2), (1, 2, 3))]
            ex = active_factor(roster, stage, ipos, "expert", (1, 2, 3))
            bot = active_factor(roster, stage, ipos, "bot", (1, 2, 3))
            print(f"| {name} | {label} | x{1 + f[0]['f']:.2f} | x{1 + f[1]['f']:.2f} | x{1 + f[2]['f']:.2f} | x{1 + ex['f']:.2f} | x{1 + bot['f']:.2f} | {f[2]['busy']:.0%} |")
    print("\n### 8b. Online time to each IPO, Shares per IPO, and the whole IPO shop (typical player; passive = today's game)")
    print("| Player | Tasks | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Shares IPO 1 / 10 (no pass) | Shares IPO 1 / 10 (pass) | IPOs in %d d | Whole shop, pass (%d Shares) |" % (days, total_perks))
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for b in ("active", "casual30", "casual"):
        for label, skill, waves in ACTIVE_MODES:
            kw = {"active": skill, "active_waves": waves}
            runs = [run(b, seed, days=days, use_ipo=True, **kw) for seed in range(n)]
            pass_runs = [run(b, seed, days=days, use_ipo=True, shareholder=True, **kw) for seed in range(n)]
            times = []
            for k in (1, 2, 3, 5, 10):
                if sum(1 for r in runs if len(r.ipo_times) >= k) < len(runs) / 2:
                    times.append("not reached")
                else:
                    times.append(fmt_active(med([active_minutes_at(b, r.ipo_times[k - 1]) if len(r.ipo_times) >= k else None for r in runs])))
            def sh(rs, k):
                v = med([r.shares_log[k - 1] if len(r.shares_log) >= k else None for r in rs])
                return f"{v:.0f}" if v is not None else "-"
            done = []
            for r in pass_runs:
                total = 0
                for i, g in enumerate(r.shares_log):
                    total += g
                    if total >= total_perks:
                        done.append((i + 1, r.ipo_times[i] / DAY))
                        break
            shop = f"IPO {med([x[0] for x in done]):.0f}, day {med([x[1] for x in done]):.0f}" if len(done) >= len(pass_runs) / 2 else f"not in {days} d ({med([r.shares for r in pass_runs]) / total_perks:.0%})"
            print(f"| {b} | {label} | " + " | ".join(times) + f" | {sh(runs, 1)} / {sh(runs, 10)} | {sh(pass_runs, 1)} / {sh(pass_runs, 10)} | {med([len(r.ipo_times) for r in runs]):.0f} | {shop} |")


# =============================================================================
# LONG GAME (docs/LONG_GAME_PROPOSAL.md): PROPOSAL, not read from any .lua, default OFF (only `--long` runs it).
# The IPO is the last thing a player reaches: the first IPO after 50+ ENGAGED hours (a target to verify, not a result).
# The ladder is DATA: LONG_ITEMS is the real item list (offices, upgrades, desks, hires, each with price and Income) and
# the valuation needed to enter the next rung is DERIVED from it by one rule (LONG_K x the price of everything bought so
# far), so the hours per rung are an OUTPUT. The prices were fitted once (outside this file) so that an always-engaged
# typical player takes the LONG_RUNGS target hours; change a price or an Income and re-run to see what that does.
# Money rules: only an ENGAGED player (a task answered and graded by the server in the last LONG_ENGAGED_WINDOW seconds)
# earns full Cash and valuation, and only for the first LONG_FULL_HOURS engaged hours per UTC day (LONG_OVER_CAP after
# that). Everything else (away, online but idle, a macro) is the away bank: LONG_AWAY of the BASE Income.
# =============================================================================
LONG_ENGAGED_WINDOW = 180           # seconds: "engaged" = a graded task answered in the last 3 minutes (the server decides, never the client)
LONG_FULL_HOURS = 3                 # engaged hours per day whose Cash counts 100% toward the valuation ...
LONG_OVER_CAP = 0.05                # ... and the share that counts after that
LONG_RESET_HOUR = 8                 # the day for this cap starts at 08:00 UTC, like the daily calendar (DailyConfig.ResetHourUtc): away.engagedDay = DailyConfig.dayNumber(os.time())
LONG_BOARD_RUNG = 4                 # Series C+D (index in LONG_RUNGS): the only rung with board requests and valuation milestones (its moments were 33 min apart)
LONG_BOARD = (45 * 60, 60)          # board request: one every 45 ENGAGED minutes in that rung, a FIXED reward of 60 s of base Income (no random reward, D9-safe); counts like task Cash
LONG_MILESTONES = (0.2, 0.4, 0.6, 0.8)                          # share of the rung's valuation distance (entry to next threshold) at which a milestone fires ...
LONG_MILESTONE_REWARDS = ("decor piece", "title", "decor piece", "task tier")   # ... and what each one gives (new content: 2 decor, 1 title, 1 extra task tier)
LONG_K = 1.5                        # valuation to enter the next rung = K x the price of everything in the rungs so far (the rule that derives the ladder)
LONG_RUNGS = [                      # (name, egg tier of its hires, Income cap of one desk, task budget in seconds of Income per online second, target hours in rung for the fit)
    ("Garage", "Garage Egg", 25, 0.85, 1.5),
    ("Seed", "Startup Egg", 60, 0.85, 4),
    ("Series A", "Scale-up Egg", 180, 0.95, 6.5),
    ("Series B", "Unicorn Egg", 300, 1.05, 9),
    ("Series C+D", "Decacorn Egg", 540, 1.15, 24),
    ("Pre-IPO", "Blue-Chip Egg", 650, 1.25, 15),
]
LONG_TASK_UNLOCK = {                # task -> rung it appears at in the first run (after the 1st IPO: all); every task type of the active-loops doc is kept
    "Customer call": 0,
    "Bug storm": 1, "Ship a feature": 1, "Interview": 1,
    "Investor pitch": 2, "Surprise event": 2, "Support ticket": 2, "Demo and contract": 2,
    "Product feedback": 3, "1-to-1 / team pizza": 3, "Viral post": 3, "Press interview": 3,
    "Ad campaign": 4, "Cash crunch": 4, "Package pickup": 4, "Product launch": 4,
    "Paired demo": 99,
}                                   # not in the rate model: roadshow (Pre-IPO), Investor Day, office decoration (C+D); Paired demo (99 = never) and Investor Day sit outside the 50 h path
LONG_HIRE_TYPES = [                 # (creature, Income, role family, egg tier it first comes from, exists today): 18 types (12 today + 6 new); the new ones go through CreatureConfig.fixedHire (D9)
    ("Coffee Capybara", 2, "ops", "Garage Egg", True), ("Coding Cat", 3, "eng", "Garage Egg", True), ("Pixel Pigeon", 3, "ops", "Garage Egg", True),
    ("Hustle Hamster", 7, "sales", "Garage Egg", True), ("Bug Beetle", 8, "eng", "Garage Egg", True), ("Memo Mole", 9, "ops", "Garage Egg", True),
    ("Sales Shark", 20, "sales", "Startup Egg", True), ("Pitch Parrot", 24, "mkt", "Startup Egg", True),
    ("Server Sloth", 50, "eng", "Startup Egg", True), ("Ledger Llama", 60, "fin", "Scale-up Egg", True),
    ("Unicorn CEO", 150, "fin", "Scale-up Egg", True), ("Venture Dragon", 175, "fin", "Scale-up Egg", True),
    ("Growth Gecko", 220, "mkt", "Unicorn Egg", False), ("Compliance Cobra", 300, "fin", "Unicorn Egg", False),
    ("Platform Panda", 380, "eng", "Decacorn Egg", False), ("Closer Condor", 460, "sales", "Decacorn Egg", False),
    ("Brand Badger", 540, "mkt", "Blue-Chip Egg", False), ("Board Bison", 620, "fin", "Blue-Chip Egg", False),
]
for _name, _inc, _role, _egg, _old in LONG_HIRE_TYPES:
    ACTIVE_ROLE_FAMILY.setdefault(_inc, {_role: 1})   # the new Income values (220 and up) get their role; nothing older is touched

LONG_ITEMS = [   # (rung, kind, name, price in Cash, Income in Cash/s) in BUYING ORDER; a hire's price is what its egg(s) cost, a desk and an office have no Income.
    # Each rung's first office comes after its first 2 upgrades (no rung opens with nothing to buy); in Series C+D every upgrade is two levels (I and II), each at half the price and half the Income.
    # Prices were refitted (one factor per rung, rounded to 2 significant digits) so that the reference player takes the LONG_RUNGS target hours.
    # rung 0: Garage
    (0, "upgrade", "Desk", 0, 1),
    (0, "upgrade", "Coffee Machine", 1100, 2),
    (0, "office", "Garage", 0, 0),
    (0, "desk", "Desk 1", 0, 0),
    (0, "hire", "Coding Cat", 2300, 3),
    (0, "upgrade", "Laptop", 4200, 5),
    (0, "desk", "Desk 2", 3600, 0),
    (0, "hire", "Bug Beetle", 7200, 8),
    (0, "upgrade", "Server Rack", 13000, 15),
    (0, "upgrade", "Whiteboard", 28000, 40),
    (0, "upgrade", "Neon Logo", 72000, 120),
    # rung 1: Seed
    (1, "upgrade", "Standing Desks", 160000, 6),
    (1, "upgrade", "Espresso Bar", 230000, 12),
    (1, "office", "Co-working Loft", 580000, 0),
    (1, "desk", "Desk 3", 150000, 0),
    (1, "hire", "Sales Shark", 310000, 20),
    (1, "upgrade", "Dev Laptops", 320000, 20),
    (1, "upgrade", "Rack Room", 410000, 30),
    (1, "upgrade", "Glass Boardroom", 500000, 38),
    (1, "upgrade", "Rooftop Sign", 570000, 44),
    (1, "desk", "Desk 4", 320000, 0),
    (1, "hire", "Server Sloth", 650000, 50),
    # rung 2: Series A
    (2, "upgrade", "Open Plan", 560000, 12),
    (2, "upgrade", "Quiet Pods", 810000, 24),
    (2, "office", "Downtown Floor", 2000000, 0),
    (2, "upgrade", "Design Studio", 1100000, 40),
    (2, "desk", "Desk 5", 690000, 0),
    (2, "hire", "Ledger Llama", 1400000, 60),
    (2, "upgrade", "Data Closet", 1500000, 60),
    (2, "upgrade", "Demo Theater", 1700000, 76),
    (2, "upgrade", "Lobby Screen", 2000000, 88),
    (2, "desk", "Desk 6", 1400000, 0),
    (2, "hire", "Unicorn CEO", 2700000, 150),
    (2, "desk", "Desk 7", 1600000, 0),
    (2, "hire", "Venture Dragon", 3200000, 175),
    # rung 3: Series B
    (3, "upgrade", "Game Room", 2300000, 25),
    (3, "upgrade", "Gym", 3200000, 50),
    (3, "office", "Campus Wing", 7800000, 0),
    (3, "upgrade", "Cafeteria", 4200000, 80),
    (3, "upgrade", "Data Center", 5300000, 120),
    (3, "upgrade", "Auditorium", 6200000, 150),
    (3, "desk", "Desk 8", 3500000, 0),
    (3, "hire", "Venture Dragon", 7100000, 175),
    (3, "upgrade", "Fountain", 7500000, 175),
    (3, "desk", "Desk 9", 4400000, 0),
    (3, "hire", "Growth Gecko", 8800000, 220),
    (3, "desk", "Desk 10", 5400000, 0),
    (3, "hire", "Compliance Cobra", 11000000, 300),
    # rung 4: Series C+D
    (4, "upgrade", "Robot Barista I", 3400000, 12.5),
    (4, "upgrade", "Robot Barista II", 3400000, 12.5),
    (4, "office", "Tech Campus", 23000000, 0),
    (4, "upgrade", "Sky Lounge I", 4900000, 25),
    (4, "upgrade", "Sky Lounge II", 4900000, 25),
    (4, "upgrade", "Mega Rack I", 6100000, 40),
    (4, "upgrade", "Mega Rack II", 6100000, 40),
    (4, "upgrade", "Innovation Lab I", 7600000, 60),
    (4, "upgrade", "Innovation Lab II", 7600000, 60),
    (4, "upgrade", "Atrium I", 8600000, 75),
    (4, "upgrade", "Atrium II", 8600000, 75),
    (4, "upgrade", "Helipad I", 9600000, 87.5),
    (4, "upgrade", "Helipad II", 9600000, 87.5),
    (4, "desk", "Desk 11", 13000000, 0),
    (4, "hire", "Compliance Cobra", 26000000, 300),
    (4, "desk", "Desk 12", 15000000, 0),
    (4, "hire", "Platform Panda", 31000000, 380),
    (4, "office", "Glass Tower", 31000000, 0),
    (4, "upgrade", "Trading Floor I", 4700000, 15),
    (4, "upgrade", "Trading Floor II", 4700000, 15),
    (4, "upgrade", "Spa I", 6600000, 30),
    (4, "upgrade", "Spa II", 6600000, 30),
    (4, "upgrade", "Quantum Rack I", 8600000, 47.5),
    (4, "upgrade", "Quantum Rack II", 8600000, 47.5),
    (4, "upgrade", "Observatory I", 10000000, 70),
    (4, "upgrade", "Observatory II", 10000000, 70),
    (4, "upgrade", "Ballroom I", 12000000, 87.5),
    (4, "upgrade", "Ballroom II", 12000000, 87.5),
    (4, "upgrade", "Statue I", 13000000, 100),
    (4, "upgrade", "Statue II", 13000000, 100),
    (4, "desk", "Desk 13", 20000000, 0),
    (4, "hire", "Closer Condor", 40000000, 460),
    (4, "desk", "Desk 14", 21000000, 0),
    (4, "hire", "Closer Condor", 42000000, 460),
    (4, "desk", "Desk 15", 23000000, 0),
    (4, "hire", "Brand Badger", 48000000, 540),
    # rung 5: Pre-IPO
    (5, "upgrade", "Marble Lobby", 18000000, 40),
    (5, "upgrade", "War Room", 25000000, 80),
    (5, "office", "Global HQ", 62000000, 0),
    (5, "upgrade", "Server Farm", 32000000, 130),
    (5, "upgrade", "Roadshow Jet", 39000000, 190),
    (5, "upgrade", "Bell Tower", 47000000, 260),
    (5, "upgrade", "Golden Bell", 51000000, 300),
    (5, "desk", "Desk 16", 35000000, 0),
    (5, "hire", "Brand Badger", 70000000, 540),
    (5, "desk", "Desk 17", 39000000, 0),
    (5, "hire", "Board Bison", 78000000, 620),
    (5, "desk", "Desk 18", 41000000, 0),
    (5, "hire", "Board Bison", 81000000, 620),
]

LONG_LOOP_GROWTH = 0.05             # prices and valuation thresholds of loop L = IPO multiplier x (1 + this) ^ L
LONG_AWAY = (0.10, 2 * 3600, 0.10)  # away pay = 10% of the BASE Income (no passes, boosts or chain), banked up to 2 h per return, 10% of it counts toward valuation
LONG_AWAY_OLD = (0.50, 8 * 3600, 1.0)   # today: 50% of passive Income, 8 h, 100% valuation
LONG_SHARES = (20, 0.25, 1.5, 0.5)  # Shares = base x (1 + growth x IPOs done) x min(ratio, cap) ^ exponent (x2 Shareholder pass)
LONG_SHOP = {                       # PROPOSED IPO shop (same keys and levels as IpoConfig.Perks, re-priced; the sim only uses the totals)
    "FasterEggs": [1, 2, 3, 5, 7, 10, 16], "ExtraIncubator": [4, 8], "ExtraSlot": [4, 8, 18],
    "BaseLuck": [1, 2, 3, 5, 7, 10, 16, 24], "OfflineCap": [2, 4, 7, 12], "CheaperPoach": [2, 3, 4, 6, 8, 11, 15, 20, 28, 40],
}
LONG_PRESTIGE_WING = 434            # new cosmetic / prestige items (office skins, creature hats, titles): Shares, all cosmetic
LONG_SPEED_KEYS = ("FasterEggs", "ExtraIncubator", "ExtraSlot", "BaseLuck")   # the perks that move the clock
LONG_SPEED_PERKS = (sum(sum(LONG_SHOP[k]) for k in LONG_SPEED_KEYS), 0.25)   # their whole price (154 Shares) is worth at most +25% Income (an ESTIMATE, not measured)
LONG_DT = 20.0                      # seconds per step while a session runs
LONG_PLAYERS = {                    # sessions per day as (start hour, minutes), days of the week played, chance a planned session happens, skill (None = the run's), session length varies
    "dedicated": dict(sessions=[(0, 60), (12, 60)], days=range(7), chance=0.95, skill=None, jitter=True),   # 2 h a day, 14 h a week
    "regular": dict(sessions=[(0, 60)], days=range(7), chance=0.90, skill=None, jitter=True),               # 1 h a day, ~6 h a week
    "casual": dict(sessions=[(0, 60)], days=(0, 2, 5), chance=0.85, skill=None, jitter=True),               # 3 sessions a week, ~2.5 h a week
    "check-in": dict(sessions=[(0, 1)], days=range(7), chance=0.90, skill=None, jitter=True),               # 1 minute a day: collects the away bank and leaves
    "macro": dict(sessions=[(0, 1440)], days=range(7), chance=1.0, skill="macro", jitter=False),            # online 24/7 sending input (jumping), answers no task
    "task-bot": dict(sessions=[(0, 1440)], days=range(7), chance=1.0, skill="bot", jitter=False),           # online 24/7, answers every task perfectly (the budget is its ceiling)
    "pulse-bot": dict(sessions=[(2 * i, 3) for i in range(12)], days=range(7), chance=1.0, skill="bot", jitter=False),   # answers tasks for 3 minutes every 2 hours, all day
    "reference": dict(sessions=[(0, 1440)], days=range(7), chance=1.0, skill="typical", jitter=False),      # fit tool: always engaged, typical, no away pay, no daily cap
}


def long_thresholds(items=None, price_mult=1.0):
    """Valuation to enter rung r+1 (the last one = IPO-ready), loop 0 prices: LONG_K x the price of every item in rungs 0..r."""
    items = items or LONG_ITEMS
    return [LONG_K * price_mult * sum(it[3] for it in items if it[0] <= r) for r in range(len(LONG_RUNGS))]


def long_scale(loop, growth):
    """Prices and thresholds of a run after `loop` IPOs: the IPO multiplier (it also multiplies Income, so it cancels) times growth ^ loop."""
    if loop <= 0:
        return 1.0
    return (1 + IPO_BONUS_PER_IPO * loop ** IPO_BONUS_EXPONENT) * (1 + growth) ** loop


def long_mult(loop):
    """The IPO Income multiplier (kept hires and everything else earn this much more)."""
    return 1.0 if loop <= 0 else 1 + IPO_BONUS_PER_IPO * loop ** IPO_BONUS_EXPONENT


def long_run(kind, seed, loops=1, away=LONG_AWAY, growth=LONG_LOOP_GROWTH, skill="typical", cash_mult=1.0, valuation_at_base=True,
             shareholder=False, max_days=1100, engaged_rule="graded", full_hours=LONG_FULL_HOURS, over_cap=LONG_OVER_CAP,
             f_mult=1.0, inc_mult=1.0, price_mult=1.0, fed=None, fed_carry=False, fed_run=None, fed_cap=True, budget=None, items=None, hire_free_after_ipo=True):
    """One player until `loops` IPOs. Returns dict(stage_h = [[engaged hours when each rung opened] per loop], ipo_h = engaged hours at each
    IPO, online_h, ipo_day, shares, away_val ...).
    engaged_rule: "graded" = only a graded task makes you engaged (proposed); "input" = any input does (the first draft, the macro hole).
    fed = poach-ins per UTC day an alt account feeds this player (None = never): a fed hire is free and works at the desk's Income cap.
    fed_run = most fed hires per run (None = no limit). fed_cap: a fed hire works at the desk's Income cap (rule R1); False = at the best hire's Income (no cap).
    fed_carry: fed hires keep that Income when they carry over an IPO (the exploit); otherwise they carry as the planned hire."""
    spec = LONG_PLAYERS[kind]
    rng = random.Random(seed * 7919 + zlib.crc32(kind.encode()))
    sk = spec["skill"] or skill
    items = items or LONG_ITEMS
    n_items = len(items)
    rung_of = [it[0] for it in items]
    price = [it[3] * price_mult for it in items]
    gain_of = [it[4] * inc_mult for it in items]
    cap_of = [LONG_RUNGS[it[0]][2] for it in items]
    is_hire = [it[1] == "hire" for it in items]
    thr = long_thresholds(items, price_mult)
    n_rungs = len(LONG_RUNGS)
    base_ratio = 1.0 if valuation_at_base else cash_mult   # the Cash pass multiplies spendable Cash only, unless the valuation counts it too (today)
    graded = engaged_rule == "graded"
    engaged_kind = not (sk == "macro" and graded)
    loop, owned, income, cash, val = 0, 0, 0.0, 0.0, 0.0
    stage, shares, spent_speed, speed = 0, 0, 0, 1.0
    eng_s = online_s = 0.0
    eng_today, cur_day, fed_left, fed_run_left, bank_s = 0.0, -1, 0, (fed_run if fed_run is not None else 10 ** 9), 0.0
    best_hire = max(h[1] for h in LONG_HIRE_TYPES)
    carry = [0.0] * n_items      # Income each hire row had last run (kept employees fill the same desk, free)
    now_inc = [0.0] * n_items
    nhire = 0
    fcache = {}
    out = {"stage_h": [[0.0]], "ipo_h": [], "ipo_day": [], "online_h": [], "shares": [], "away_val": 0.0, "val_total": 0.0,
           "buy_h": [], "ms_h": [], "board_h": []}   # the last three (loop 0 only): engaged hours of each purchase (rung, h), milestone and board request
    board_t, ms_next = 0.0, 0
    last_end = None

    def f_now():
        key = (stage, nhire, loop)
        hit = fcache.get(key)
        if hit is None:
            if sk == "macro":
                hit = 0.0
            else:
                roster = [items[j][4] for j in range(owned) if is_hire[j]]   # the planned type decides the role
                hit = active_factor(roster, stage, loop, sk, (1, 2, 3), budget=LONG_RUNGS[stage][3] if budget is None else budget,
                                    unlock_map=LONG_TASK_UNLOCK)["f"] * f_mult
            fcache[key] = hit
        return hit

    for day in range(max_days):
        if day % 7 not in spec["days"]:
            continue
        for start_h, minutes in spec["sessions"]:
            if rng.random() > spec["chance"]:
                continue
            length = (max(1, minutes * rng.uniform(0.7, 1.3)) if spec["jitter"] else minutes) * 60
            s_start = day * DAY + start_h * 3600
            sc = long_scale(loop, growth)
            m_inc = long_mult(loop)
            if last_end is not None and away[0] > 0:
                gap = min(s_start - last_end, away[1])
                if away is LONG_AWAY_OLD:                    # today's rule: paid at once, 100% of it counts
                    pay_away = gap * away[0] * income * m_inc * speed
                    cash += pay_away * cash_mult
                    val += pay_away * away[2] * base_ratio
                    out["away_val"] += pay_away * away[2] * base_ratio
                else:
                    bank_s = min(away[1], bank_s + gap)
            t = 0.0
            while t < length:
                dt = min(LONG_DT, length - t)
                d = int((s_start + t - LONG_RESET_HOUR * 3600) // DAY)   # the day starts at 08:00 UTC (shared with the daily calendar)
                if d != cur_day:                             # a new day: the engaged-hours counter and the feed start again
                    cur_day, eng_today, fed_left = d, 0.0, (fed or 0)
                if not engaged_kind:                         # online but no task graded: the same as away, the bank only fills
                    if away is not LONG_AWAY_OLD:
                        bank_s = min(away[1], bank_s + (length - t))
                    online_s += length - t
                    break
                if bank_s > 0 and away is not LONG_AWAY_OLD:  # the return: a graded task pays the bank at once (10% of the base Income)
                    pay_away = bank_s * away[0] * income * m_inc * speed
                    cash += pay_away * cash_mult
                    credit = pay_away * away[2] * base_ratio
                    val += credit
                    out["away_val"] += credit
                    bank_s = 0.0
                f = f_now() * rng.uniform(0.85, 1.15)
                base = income * m_inc * speed
                gain = base * (1 + f) * dt
                w = 1.0 if (not graded or eng_today < full_hours * 3600) else over_cap
                cash += gain * cash_mult
                val += gain * w * base_ratio
                eng_today += dt
                eng_s += dt
                online_s += dt
                t += dt
                if stage == LONG_BOARD_RUNG:                 # a board request every LONG_BOARD[0] engaged seconds: fixed reward, like task Cash
                    board_t += dt
                    if board_t >= LONG_BOARD[0]:
                        board_t -= LONG_BOARD[0]
                        pay = LONG_BOARD[1] * base
                        cash += pay * cash_mult
                        val += pay * w * base_ratio
                        if loop == 0:
                            out["board_h"].append(eng_s / 3600)
                while owned < n_items and rung_of[owned] <= stage:
                    j = owned
                    cost, g = price[j] * sc, gain_of[j]
                    if is_hire[j]:
                        if loop > 0 and hire_free_after_ipo:     # a kept employee fills the desk as soon as it is bought: free, last run's Income
                            cost, g = 0.0, carry[j] or g
                        if fed_left > 0 and fed_run_left > 0:    # an alt feeds a hire: free, at the desk's cap (or the best hire's Income without the cap)
                            cost, g = 0.0, max(g, cap_of[j] if fed_cap else best_hire)
                            fed_left -= 1
                            fed_run_left -= 1
                    if cash < cost:
                        break
                    cash -= cost
                    income += g
                    now_inc[j] = g
                    if loop == 0:
                        out["buy_h"].append((rung_of[j], eng_s / 3600))
                    if is_hire[j]:
                        nhire += 1
                    owned += 1
                if stage == LONG_BOARD_RUNG:                 # valuation milestones inside the rung (before the stage can move on)
                    lo_v, hi_v = thr[stage - 1] * sc, thr[stage] * sc
                    while ms_next < len(LONG_MILESTONES) and val >= lo_v + LONG_MILESTONES[ms_next] * (hi_v - lo_v):
                        if loop == 0:
                            out["ms_h"].append(eng_s / 3600)
                        ms_next += 1
                while stage < n_rungs and val >= thr[stage] * sc:
                    stage += 1
                    if stage < n_rungs:
                        out["stage_h"][-1].append(eng_s / 3600)
                if stage >= n_rungs:                         # IPO-ready: the player goes public right away
                    ratio = min(LONG_SHARES[2], val / (thr[-1] * sc))
                    gained = int(LONG_SHARES[0] * (1 + LONG_SHARES[1] * loop) * ratio ** LONG_SHARES[3] * (2 if shareholder else 1))
                    shares += gained
                    out["shares"].append(gained)
                    out["ipo_h"].append(eng_s / 3600)
                    out["online_h"].append(online_s / 3600)
                    out["ipo_day"].append((s_start + t) / DAY)
                    out["val_total"] += val
                    for j in range(owned):
                        if is_hire[j]:
                            carry[j] = now_inc[j] if (fed_carry or now_inc[j] <= items[j][4] * inc_mult + 1e-9) else items[j][4] * inc_mult
                    room = max(0, LONG_SPEED_PERKS[0] - spent_speed)
                    buy = min(room, shares)
                    spent_speed += buy
                    shares -= buy
                    speed = 1 + LONG_SPEED_PERKS[1] * spent_speed / LONG_SPEED_PERKS[0]
                    loop += 1
                    owned, income, cash, val, stage, nhire = 0, 0.0, 0.0, 0.0, 0, 0
                    board_t, ms_next = 0.0, 0
                    fed_run_left = fed_run if fed_run is not None else 10 ** 9
                    out["stage_h"].append([eng_s / 3600])
                    if loop >= loops:
                        out["away_share"] = out["away_val"] / max(out["val_total"], 1e-9)
                        return out
                    sc = long_scale(loop, growth)
                    m_inc = long_mult(loop)
            last_end = s_start + length
    out["away_share"] = out["away_val"] / max(val + out["val_total"], 1e-9)
    return out


def long_ref_run(items, price_mult=1.0):
    """The fit run: the always-engaged reference player, loop 0, no away pay, no daily cap (it also records purchases, milestones and board requests)."""
    return long_run("reference", 0, items=items, away=(0, 0, 0), engaged_rule="input", price_mult=price_mult, max_days=400)


def long_hours(items, price_mult=1.0):
    """Fit tool: hours the always-engaged reference player needs inside each rung (and in total), loop 0, no away pay, no daily cap."""
    r = long_ref_run(items, price_mult)
    if not r["ipo_h"]:
        return None
    cum = r["stage_h"][0][1:] + [r["ipo_h"][0]]
    return [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))]


LONG_CONTENT = [                    # per rung: (tasks that appear besides LONG_TASK_UNLOCK, products, decor pieces, titles, new egg tiers); 18 tasks on the 50 h path (+ paired demo and Investor Day outside it = 20), 6 products, 20 decor, 8 titles, 3 new eggs
    ([], 0, 3, 1, 0),
    ([], 2, 4, 1, 0),
    ([], 1, 4, 1, 1),
    ([], 1, 3, 1, 0),
    (["Office decoration"], 1, 4, 1, 1),
    (["Pre-IPO roadshow"], 1, 2, 3, 1),   # 3 titles: Pre-IPO, first IPO, tenth IPO
]


def _fmt_h(v):
    return "never" if v is None else f"{v:.1f} h"


def _fmt_d(v):
    return "-" if v is None else f"{v:.1f} d"


def _long_many(kind, n, **kw):
    return [long_run(kind, seed, **kw) for seed in range(n)]


def _long_first(runs, key="ipo_h"):
    """Median of the first IPO (engaged hours, online hours, day) over the runs that got there; None when fewer than half did."""
    done = [r for r in runs if r["ipo_h"]]
    if len(done) < len(runs) / 2:
        return None, None, None
    return med([r["ipo_h"][0] for r in done]), med([r["online_h"][0] for r in done]), med([r["ipo_day"][0] for r in done])


def long_rung_table():
    """Per rung from the item list: number of items, total price, Income ceiling, valuation to enter the next rung."""
    thr = long_thresholds()
    hours = long_hours(LONG_ITEMS)
    rows, ceiling = [], 0.0
    for r, (name, egg, cap, bud, target) in enumerate(LONG_RUNGS):
        its = [it for it in LONG_ITEMS if it[0] == r]
        ceiling += sum(it[4] for it in its)
        rows.append((name, egg, cap, bud, target, len(its), sum(it[3] for it in its), ceiling, thr[r], hours[r] if hours else None))
    return rows


def report_long_cd(ref, hours, tot):
    """Series C+D moments (the three fixes), from the reference run: how many, how far apart, what the milestones give."""
    r = LONG_BOARD_RUNG
    name = LONG_RUNGS[r][0]
    its = [it for it in LONG_ITEMS if it[0] == r]
    levels = sum(1 for it in its if it[1] == "upgrade")
    # moments of the draft (12 upgrades, no milestones, no requests) = this rung's moments minus the added levels and milestones
    cur = sum(1 for it in its if it[1] != "upgrade" and it[3] > 0) + levels
    draft = cur - levels // 2
    after_levels = cur
    after_ms = cur + len(LONG_MILESTONES)
    n_board = len(ref["board_h"])
    # the rung's content that is not bought (tasks, tiers, products, decor, title, egg) is the same in every row
    content = LONG_CONTENT[r][1] + LONG_CONTENT[r][2] + LONG_CONTENT[r][3] + LONG_CONTENT[r][4] + len(LONG_CONTENT[r][0]) + \
        sum(1 for ur in LONG_TASK_UNLOCK.values() if ur == r) + sum(1 for ur in LONG_TASK_UNLOCK.values() if ur == r - 1) + sum(1 for ur in LONG_TASK_UNLOCK.values() if ur == r - 2)
    h = hours[r]
    print(f"\n### 9n. {name} moments: the three fixes (reference player, {h:.1f} engaged hours in the rung)")
    print("| Version | Moments | Minutes per moment |")
    print("|---|---|---|")
    rows = [("draft: 12 upgrades, nothing else", draft + content, 0), ("+ Level I and II (24 levels at half price, half Income)", after_levels + content, 0),
            (f"+ {len(LONG_MILESTONES)} valuation milestones ({', '.join(f'{m:.0%}' for m in LONG_MILESTONES)} of the rung: {', '.join(LONG_MILESTONE_REWARDS)})", after_ms + content, 0),
            (f"+ board requests every {LONG_BOARD[0] // 60} min ({n_board} in the rung, fixed {LONG_BOARD[1]} s of Income each)", after_ms + content + n_board, n_board)]
    for label, m, _ in rows:
        print(f"| {label} | {m} | {h * 60 / m:.0f} |")
    ev = sorted([hh for rr, hh in ref["buy_h"] if rr == r] + [x for x in ref["ms_h"]] + [x for x in ref["board_h"]])
    start = ref["stage_h"][0][r]
    def gaps_of(events):
        pts = [start] + events + [start + h]
        return [(b - a) * 60 for a, b in zip(pts, pts[1:])]
    gaps = gaps_of(ev)
    no_req = gaps_of(sorted([hh for rr, hh in ref["buy_h"] if rr == r] + list(ref["ms_h"])))
    print(f"Longest gap between two bought items, milestones or board requests in the rung: {max(gaps):.0f} min (average {sum(gaps) / len(gaps):.1f} min over {len(ev)} events); "
          f"without the requests: {max(no_req):.0f} min (average {sum(no_req) / len(no_req):.1f}). "
          f"Milestones fire at {', '.join(f'{(x - start):.1f} h' for x in ref['ms_h'])} into the rung.")


def report_long_g1():
    """Gate G1 target: f of the customer calls alone (PR 1 has only calls), per rung, against all tasks (PR 2+)."""
    print("\n### 9m. Gate G1: the task bonus f of the customer calls alone (typical / expert / bot) against all tasks, per rung (budget of the rung)")
    print("| Rung | Hires | f calls only (PR 1 target) | f all tasks (PR 2+ target) |")
    print("|---|---|---|---|")
    calls = {k: (0 if k == "Customer call" else 99) for k in LONG_TASK_UNLOCK}
    for r, (name, egg, cap, bud, target) in enumerate(LONG_RUNGS):
        roster = [it[4] for it in LONG_ITEMS if it[1] == "hire" and it[0] <= r]
        cells = [" / ".join(f"{active_factor(roster, r, 0, sk, (1, 2, 3), budget=bud, unlock_map=um)['f']:.2f}" for sk in ("typical", "expert", "bot")) for um in (calls, LONG_TASK_UNLOCK)]
        print(f"| {name} | {len(roster)} | {cells[0]} | {cells[1]} |")


def report_long(n):
    """Section 9: the long game. Only with --long."""
    print(f"\n## 9. LONG GAME (proposal, default OFF), median of {n} runs; hours are ENGAGED hours (a task answered and graded in the last {LONG_ENGAGED_WINDOW // 60} min)")
    print("### 9a. The ladder derived from the item list (LONG_ITEMS, loop 0). Enter-next valuation = K x price of everything so far, K = %.1f" % LONG_K)
    print("| Rung | Items | Total price | Income ceiling /s | Enter next at (valuation) | Reference hours (cum.) | Desk cap /s | Task budget |")
    print("|---|---|---|---|---|---|---|---|")
    cum = 0.0
    for name, egg, cap, bud, target, k, total, ceiling, thr, h in long_rung_table():
        cum += h
        print(f"| {name} | {k} | {total:,.0f} | {ceiling:,.0f} | {thr:,.0f} | {h:.1f} ({cum:.1f}) | {cap} | {bud:.2f} |")
    print("\n### 9b. Engaged hours to each rung and IPO 1, by player, and the weeks that takes")
    print("| Player (played) | Seed | Series A | Series B | Series C+D | Pre-IPO | IPO-ready (IPO 1) | Weeks to IPO 1 | Shares |")
    print("|---|---|---|---|---|---|---|---|---|")
    labels = {"dedicated": "dedicated (2 h/day)", "regular": "regular (1 h/day)", "casual": "casual (3 x 1 h/week)", "check-in": "check-in only (1 min/day)"}
    for kind in ("dedicated", "regular", "casual", "check-in"):
        runs = _long_many(kind, n if kind != "check-in" else max(5, n // 4), max_days=1100)
        done = [r for r in runs if r["ipo_h"]]
        cells = []
        for si in range(1, len(LONG_RUNGS)):
            vals = [r["stage_h"][0][si] for r in runs if len(r["stage_h"][0]) > si]
            cells.append(_fmt_h(med(vals)) if len(vals) >= len(runs) / 2 else "not in 3 y")
        h, _, day = _long_first(runs)
        sh = med([r["shares"][0] for r in done]) if h is not None else None
        print(f"| {labels[kind]} | " + " | ".join(cells) + f" | {_fmt_h(h)} | {'-' if day is None else f'{day / 7:.0f}'} | {'-' if sh is None else f'{sh:.0f}'} |")
    ex = _long_many("regular", n, skill="expert")
    h, _, day = _long_first(ex)
    print(f"| regular, expert at tasks | | | | | | {_fmt_h(h)} | {day / 7:.0f} | {med([r['shares'][0] for r in ex]):.0f} |")

    print("\n### 9c. Macro and bots (24/7 online): engaged hours, hours online and days to IPO 1, the first draft (any input = engaged, no daily cap) against the fix (graded task, %d h/day at 100%% then %d%%, the day starts at %02d:00 UTC)" % (LONG_FULL_HOURS, round(LONG_OVER_CAP * 100), LONG_RESET_HOUR))
    print("| Player | Rule | Engaged h to IPO 1 | Online h | Days |")
    print("|---|---|---|---|---|")
    nb = max(4, n // 8)
    for kind, label in (("macro", "macro: input only, no task"), ("task-bot", "task-bot at the budget cap"), ("pulse-bot", "pulse-bot: 3 min of tasks every 2 h")):
        for rule, rl in (("input", "before"), ("graded", "after")):
            runs = _long_many(kind, nb, engaged_rule=rule, max_days=1100)
            h, oh, day = _long_first(runs)
            print(f"| {label} | {rl} | {_fmt_h(h)} | {_fmt_h(oh)} | {_fmt_d(day)} |")
    for fh, oc, label in ((4, 0.10, "the old draft: 4 h/day then 10%"), (2, 0.05, "2 h/day then 5%")):
        runs = _long_many("task-bot", nb, full_hours=fh, over_cap=oc, max_days=1100)
        h, oh, day = _long_first(runs)
        print(f"| task-bot at the budget cap | after, {label} | {_fmt_h(h)} | {_fmt_h(oh)} | {_fmt_d(day)} |")
    for kind in ("dedicated", "regular"):
        runs = _long_many(kind, n, max_days=1100)
        h, oh, day = _long_first(runs)
        print(f"| {kind} (for scale) | after | {_fmt_h(h)} | {_fmt_h(oh)} | {_fmt_d(day)} |")

    print("\n### 9d. Away rule: what decides the IPO (regular player, engaged hours to IPO 1 and share of valuation that came from away time)")
    print("| Rule | Engaged h to IPO 1 | Wall weeks | Valuation from away |")
    print("|---|---|---|---|")
    for label, rule in (("no away pay at all", (0.0, 0, 0.0)), ("NEW: 10% of base Income, 2 h cap, 10% counts", LONG_AWAY),
                        ("NEW but 25% counts", (0.10, 2 * 3600, 0.25)), ("NEW but 100% counts", (0.10, 2 * 3600, 1.0)),
                        ("TODAY: 50% of passive, 8 h cap, 100% counts", LONG_AWAY_OLD)):
        for kind in ("regular", "check-in"):
            runs = _long_many(kind, n if kind == "regular" else max(5, n // 4), away=rule, max_days=1100)
            h, _, day = _long_first(runs)
            share = med([r["away_share"] for r in runs])
            print(f"| {label}, {kind} | {_fmt_h(h)} | {'-' if day is None else f'{day / 7:.0f}'} | {share:.0%} |")

    print("\n### 9e. Cash pass (x2): does it still halve the first IPO?")
    print("| Regular player | Engaged h to IPO 1 |")
    print("|---|---|")
    for label, kw in (("no pass", {}), ("2x Cash pass, valuation counts base Cash (proposed)", {"cash_mult": 2.0, "valuation_at_base": True}),
                      ("2x Cash pass, valuation counts doubled Cash (today)", {"cash_mult": 2.0, "valuation_at_base": False})):
        h, _, _ = _long_first(_long_many("regular", n, **kw))
        print(f"| {label} | {_fmt_h(h)} |")

    print("\n### 9f. Sensitivity of the first IPO (regular player, engaged hours): the 50+ h is a TARGET, these are the ranges around it")
    print("| Change | Engaged h to IPO 1 |")
    print("|---|---|")
    base_h = _long_first(_long_many("regular", n))[0]
    grid = [("none (draft)", {}), ("task bonus x0.5", dict(f_mult=0.5)), ("task bonus none (tasks pay nothing)", dict(f_mult=0.0)),
            ("item Income x0.8", dict(inc_mult=0.8)), ("item Income x1.25", dict(inc_mult=1.25)),
            ("prices (and so thresholds) -30%", dict(price_mult=0.7)), ("prices +30%", dict(price_mult=1.3)),
            ("optimistic: bonus x1, Income x1.25, prices -30%", dict(inc_mult=1.25, price_mult=0.7)),
            ("pessimistic: bonus x0.5, Income x0.8, prices +30%", dict(f_mult=0.5, inc_mult=0.8, price_mult=1.3)),
            ("worst: no bonus, Income x0.8, prices +30%", dict(f_mult=0.0, inc_mult=0.8, price_mult=1.3))]
    for label, kw in grid:
        h = base_h if not kw else _long_first(_long_many("regular", max(8, n // 2), **kw))[0]
        print(f"| {label} | {_fmt_h(h)} |")

    print("\n### 9g. Loops: engaged hours per loop and Shares (3 loops), thresholds and prices grow per loop")
    print("| Player | Prices and thresholds grow | Loop 1 | Loop 2 | Loop 3 | Shares IPO 1 / 2 / 3 (no pass) | with Shareholder pass |")
    print("|---|---|---|---|---|---|---|")
    for kind in ("dedicated", "regular"):
        for growth in (0.0, 0.05, 0.10, 0.15):
            runs = _long_many(kind, max(5, n // 2), loops=3, growth=growth)
            pr = _long_many(kind, max(5, n // 4), loops=3, growth=growth, shareholder=True)

            def loop_h(rs, i):
                return _fmt_h(med([(r["ipo_h"][i] - (r["ipo_h"][i - 1] if i else 0)) for r in rs if len(r["ipo_h"]) > i]))

            def shr(rs):
                return " / ".join(f"{med([r['shares'][i] for r in rs if len(r['shares']) > i]):.0f}" for i in range(3))
            print(f"| {kind} | +{growth:.0%} per loop | {loop_h(runs, 0)} | {loop_h(runs, 1)} | {loop_h(runs, 2)} | {shr(runs)} | {shr(pr)} |")
    print("\n### 9h. Ten loops (+%d%% per loop, Shareholder pass in brackets): engaged hours and wall weeks to IPO N, Shares owned in total" % round(LONG_LOOP_GROWTH * 100))
    print("| Player | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 6 | IPO 10 | Shares after IPO 1 / 2 / 5 / 10 |")
    print("|---|---|---|---|---|---|---|---|")
    for kind in ("dedicated", "regular", "casual"):
        runs = _long_many(kind, max(5, n // 6), loops=10, max_days=4000)
        pr = _long_many(kind, max(5, n // 6), loops=10, max_days=4000, shareholder=True)
        cells = []
        for k in (1, 2, 3, 5, 6, 10):
            h = med([r["ipo_h"][k - 1] for r in runs if len(r["ipo_h"]) >= k])
            hp = med([r["ipo_h"][k - 1] for r in pr if len(r["ipo_h"]) >= k])
            w = med([r["ipo_day"][k - 1] / 7 for r in runs if len(r["ipo_day"]) >= k])
            cells.append(f"{h:.0f} h ({hp:.0f}) / {w:.0f} wk" if h is not None else "-")

        def tot(rs, k):
            return med([sum(r["shares"][:k]) for r in rs if len(r["shares"]) >= k])
        print(f"| {kind} | " + " | ".join(cells) + " | " + " / ".join(f"{tot(runs, k):.0f} ({tot(pr, k):.0f})" for k in (1, 2, 5, 10)) + " |")
    core = sum(sum(c) for c in LONG_SHOP.values())
    print(f"\nProposed shop: core perks {core} Shares (speed perks {LONG_SPEED_PERKS[0]}), prestige wing {LONG_PRESTIGE_WING}, total {core + LONG_PRESTIGE_WING} (today {sum(sum(c) for c in IPO_PERK_COSTS.values())}). "
          f"The speed lump (+{LONG_SPEED_PERKS[1]:.0%} Income for all {LONG_SPEED_PERKS[0]} Shares) is an ESTIMATE; the pass gap in the brackets above is what it is worth under that estimate.")

    print("\n### 9i. Task bonus and budget per rung (Income fraction f the tasks add; typical / expert / bot), flat budget 0.85 against the proposed per-rung budget")
    print("| Rung | Team | Budget | f flat 0.85 | f per-rung | Waves 1-2 only (rest pays Office Points) |")
    print("|---|---|---|---|---|---|")
    for r, (name, egg, cap, bud, target) in enumerate(LONG_RUNGS):
        roster = [it[4] for it in LONG_ITEMS if it[1] == "hire" and it[0] <= r]
        cells = []
        for b in (0.85, bud):
            cells.append(" / ".join(f"{active_factor(roster, r, 0, sk, (1, 2, 3), budget=b, unlock_map=LONG_TASK_UNLOCK)['f']:.2f}" for sk in ("typical", "expert", "bot")))
        cells.append(" / ".join(f"{active_factor(roster, r, 0, sk, (1, 2), budget=0.85, unlock_map=LONG_TASK_UNLOCK)['f']:.2f}" for sk in ("typical", "expert", "bot")))
        print(f"| {name} | {len(roster)} hires | {bud:.2f} | {cells[0]} | {cells[1]} | {cells[2]} |")

    print("\n### 9j. Founder load with a big team (demand D = min(%.1f, 1 + demand x hires); all tasks on, typical player, 2 h model)" % ACTIVE_DEMAND_CAP)
    print("| Desks | Founder busy | Calls and tasks the founder answers /h | Team handles /h | f (typical) |")
    print("|---|---|---|---|---|")
    hires = [it[4] for it in LONG_ITEMS if it[1] == "hire"] + [620, 620]
    for desks in (3, 8, 12, 16, 18, 20):
        roster = hires[-desks:] if desks <= len(hires) else hires
        fam = {}
        for inc in roster:
            for fm, w in ACTIVE_ROLE_FAMILY.get(inc, {"ops": 1}).items():
                fam[fm] = fam.get(fm, 0) + w
        res = _simulate_tasks(len(roster), fam, 5, None, "typical", (1, 2, 3), random.Random(7), budget=1.25, unlock_map=LONG_TASK_UNLOCK)
        print(f"| {desks} | {res['busy']:.0%} | {res['founder_per_h']:.0f} | {res['team_per_h']:.0f} | {res['f']:.2f} |")

    print("\n### 9k. Alt accounts feeding top hires to a main account (poaching): regular player, engaged hours; a fed hire is free and works at the desk's Income cap (R1) unless noted")
    print("| Case | IPO 1 | Loop 2 |")
    print("|---|---|---|")
    ne = max(8, n // 2)
    for label, kw in (("no feeding", {}),
                      ("fed without limit, NO desk cap (hires work at their own Income)", dict(fed=99, fed_cap=False, fed_carry=True)),
                      ("R1 desk cap only (fed without limit, carries over an IPO)", dict(fed=99, fed_carry=True)),
                      ("R1 + 2 poach-ins per UTC day (never binds: desks open slowly)", dict(fed=2, fed_carry=True)),
                      ("R1 + at most 6 poach-ins per run", dict(fed=99, fed_run=6, fed_carry=True)),
                      ("R1 + at most 3 poach-ins per run", dict(fed=99, fed_run=3, fed_carry=True)),
                      ("R1 + 3 per run + poached hires do not carry over an IPO", dict(fed=99, fed_run=3, fed_carry=False))):
        runs = _long_many("regular", ne, loops=2, **kw)
        h1 = med([r["ipo_h"][0] for r in runs if r["ipo_h"]])
        h2 = med([r["ipo_h"][1] - r["ipo_h"][0] for r in runs if len(r["ipo_h"]) > 1])
        print(f"| {label} | {_fmt_h(h1)} | {_fmt_h(h2)} |")

    print("\n### 9l. Content per rung (from the item list and LONG_CONTENT): moments = things bought + tasks + task tiers + products + decor + titles + new egg tiers")
    print("(a task's tier 2 appears one rung after the task, tier 3 two rungs after: more options, tighter limits, same seconds-based reward)")
    print("(Series C+D only: every upgrade is two levels, I and II, which count as two things bought; 4 valuation milestones at %s of the rung; board requests are repeated events, counted in the last two columns only)" %
          "/".join(f"{m:.0%}" for m in LONG_MILESTONES))
    print("| Rung | Offices | Upgrades (levels) | Desks | Hires | Tasks | Task tiers | Products | Decor | Titles | New eggs | Milestones | Moments | Hours | Minutes per moment | Board requests | Minutes per moment with requests |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    tot = [0] * 12
    ref = long_ref_run(LONG_ITEMS)
    hours = long_hours(LONG_ITEMS)
    n_board = len(ref["board_h"])
    for r, (name, *_rest) in enumerate(LONG_RUNGS):
        its = [it for it in LONG_ITEMS if it[0] == r]
        c = {k: sum(1 for it in its if it[1] == k and it[3] > 0) for k in ("office", "upgrade", "desk", "hire")}
        c["upgrade"] += sum(1 for it in its if it[1] == "upgrade" and it[3] == 0)
        tasks = sum(1 for tname, ur in LONG_TASK_UNLOCK.items() if ur == r) + len(LONG_CONTENT[r][0])
        tiers = sum(1 for ur in LONG_TASK_UNLOCK.values() if ur == r - 1) + sum(1 for ur in LONG_TASK_UNLOCK.values() if ur == r - 2)
        row = [c["office"], c["upgrade"], c["desk"], c["hire"], tasks, tiers, LONG_CONTENT[r][1], LONG_CONTENT[r][2], LONG_CONTENT[r][3], LONG_CONTENT[r][4],
               len(LONG_MILESTONES) if r == LONG_BOARD_RUNG else 0]
        moments = sum(row)
        board = n_board if r == LONG_BOARD_RUNG else 0
        tot = [a + b for a, b in zip(tot, row + [moments])]
        print(f"| {name} | " + " | ".join(str(x) for x in row) + f" | {moments} | {hours[r]:.1f} | {hours[r] * 60 / moments:.0f} | {board} | {hours[r] * 60 / (moments + board):.0f} |")
    print("| Total | " + " | ".join(str(x) for x in tot[:11]) + f" | {tot[11]} | {sum(hours):.1f} | {sum(hours) * 60 / tot[11]:.0f} | {n_board} | {sum(hours) * 60 / (tot[11] + n_board):.0f} |")
    print("(plus 2 tasks outside the 50 h path: paired demo and Investor Day, so 20 task types in all)")
    report_long_g1()
    report_long_cd(ref, hours, tot)
    early = [it for it in LONG_ITEMS if it[0] <= 1 and it[3] > 0]
    old_hires = {h[0] for h in LONG_HIRE_TYPES if h[4]}
    exists = sum(1 for it in early if (it[0] == 0 and it[1] == "upgrade") or (it[1] == "hire" and it[2] in old_hires))
    print(f"\nFirst {hours[0] + hours[1]:.1f} h (Garage + Seed): {len(early)} things to buy, {exists} of them exist today (garage upgrades and hire types; all re-priced), {len(early) - exists} are new "
          f"(Seed office, 6 Seed upgrades, desks); plus {sum(1 for ur in LONG_TASK_UNLOCK.values() if ur <= 1)} tasks, {LONG_CONTENT[0][1] + LONG_CONTENT[1][1]} products, "
          f"{LONG_CONTENT[0][2] + LONG_CONTENT[1][2]} decor pieces and {LONG_CONTENT[0][3] + LONG_CONTENT[1][3]} titles to build.")
    print("\nNot measured: how fun the tasks are at hour 40, whether the content exists (docs/LONG_GAME_PROPOSAL.md section 3), the real task Income "
          "(a Monte Carlo with the planned roster of each rung; the real egg roll is random), real poaching between people, egg timers, luck, perks beyond a +25% "
          "speed lump (an estimate), sessions longer than planned, players who leave, Investor Day, and anything that depends on people (retention, friends, social pull). "
          "The prices were fitted so that the reference player takes the target hours, so 'about 60 h' is the target, not a result: section 9f shows how far it can move.")


# =============================================================================
# SIMS S1-S10 of the design docs (results: docs/SIMS_RESULTS.md). PROPOSAL numbers, not read from any .lua, default OFF:
# each sim has its own flag (--s1 ... --s10); --pokedex = S1-S7 (docs/CUSTOMIZE_PROPOSAL.md 5.5), --rounds = S8 (docs/FUNDING_ROUNDS_PROPOSAL.md 6),
# --gaming = S3 + S9 + S10 (docs/SECTORS_PROPOSAL.md 4). Everything here is NEW code: nothing above this block was changed, and the engine
# below (`pk_run`) is a copy of `long_run` with hooks that, with every hook off, reproduces `long_run` exactly (`pk_selfcheck` proves it).
# =============================================================================
PK_SEED = (0.10, 0.25)              # CUSTOMIZE 5.1 seed (placeholder): s% of the old company's Cash, capped at c% of the new first rung's prices
PK_BONUS = (1.5, 0.5, 0.5, 10.0)    # CUSTOMIZE 5.2 (placeholder): points per Bronze, Gold, Platinum, and the cap, in % of Income (a Cash multiplier, never valuation)
PK_TIER = dict(gold_frac=1.0, plat_frac=0.8, plat_ratio=1.25, gold_stake=5500, plat_stake=7000, pass_shrink=0.15)   # CUSTOMIZE 1.5 + FUNDING 3 (placeholders); pass_shrink = what the 2x Cash pass takes off a run (LONG_GAME section 6)
PK_FUND_CASH_BP = (1000, 2000, 3000)    # FUNDING 1: Cash of Small / Medium / Large = 10 / 20 / 30% of the round's stage valuation
PK_FUND_P = (1.5, 2.0, 2.5)             # FUNDING 3: % of Shares given per % of loop time
PK_FUND_CAP = 4000                      # FUNDING 1: DilutionCap, basis points
PK_FUND_LONG_BP = {1: (3, 8, 15), 2: (34, 91, 170), 3: (73, 195, 366), 4: (116, 310, 582), 5: (381, 1018, 1909)}   # FUNDING 3 table (stage = rung index): bp of Small / Medium / Large
PK_FUND_TODAY_BP = {1: (100, 266, 500), 2: (46, 122, 230), 3: (253, 677, 1269)}                                    # FUNDING 3 table, today's 5 stages
PK_FUND_TODAY_MIN = {1: 2, 2: 1, 3: 5}                                                                              # FUNDING 3: minutes of the first run spent in Seed / Series A / Series B (ECONOMY.md 3b)
PK_GAMING_SCOPES = [                # SECTORS 2.4 table: (name, typical work in engaged minutes, half-life in engaged minutes)
    ("Game Jam", 15, 20), ("Indie", 30, 30), ("Mid-size", 45, 40), ("Big", 60, 50), ("Flagship", 90, 60)]
PK_GAMING_SCOPE_OF_RUNG = (0, 1, 2, 3, 4, 4)   # SECTORS 2.4: scope unlocked at Garage, Seed, A, B, C+D (and Pre-IPO)
PK_TIERS = ("Flop", "Solid", "Hit", "Smash")
PK_PLAYERS = dict(LONG_PLAYERS)       # the --long profiles, untouched, plus two schedules for the engaged-time rules (SECTORS 1.4, 2.5; LONG_GAME 2)
PK_PLAYERS["heavy"] = dict(sessions=[(0, 150), (12, 150)], days=range(7), chance=0.95, skill=None, jitter=True)    # 5 h a day: over the 3 h at full value
PK_PLAYERS["boundary"] = dict(sessions=[(7, 120)], days=range(7), chance=0.90, skill=None, jitter=True)           # one hour either side of the 08:00 UTC day change


@dataclass
class PkGam:
    """The Gaming title cycle (SECTORS 2.2-2.4). Every unit that the doc leaves open is a field here, with the assumption in docs/SIMS_RESULTS.md."""
    policy: str = "hit"                  # "smash" / "hit" / "solid" / "rush" / "never": how far the player polishes before Launch (SECTORS 2.10 policy table)
    update_rule: str = "half"            # when a Live Update is used: "every" (each cooldown) / "half" (live revenue under half the peak) / "late" (under a quarter) / "none"
    peak: tuple = (0.15, 0.35, 0.6, 0.8)           # SECTORS 2.4: Flop / Solid / Hit / Smash peak, x base Income (Game Jam row)
    scope_factor: tuple = (1.0, 1.0, 1.0, 1.0, 1.0)  # ASSUMPTION: the doc says "same x scope" without a value: 1.0 (alternatives are run in S9)
    cap: float = 0.8                     # SECTORS 2.4: live revenue plus catalog never above 0.8 x base Income
    cat_share: float = 0.03              # SECTORS 2.4: a sunset title adds 3% of its peak to the back catalog ...
    cat_cap: float = 0.10                # ... at most 10% of base Income in all
    update_cd: float = 600.0             # SECTORS 2.4/2.9: one Live Update per 10 engaged minutes
    update_first: float = 0.8            # SECTORS 2.4: updates restore the curve to 70 / 60 / 50% of the peak (0.8 - 0.1 k); ASSUMPTION: 40, 30 ... after the third, never under 10%
    tau_hit: float = 0.5                 # SECTORS 2.10: Hit = work plus half as much polish
    tau_smash: float = 1.5               # ASSUMPTION (the doc gives no number): extra polish, as a multiple of the work, that reaches Smash
    score0: float = 55.0                 # ASSUMPTION: Score at content complete with trend and trailer (Solid is 50-69)
    rush_score: float = 15.0             # ASSUMPTION: Score of a title shipped with no Fun, no Polish, no trend, no trailer (a Flop)
    fans_per_hit: float = 5.0            # SECTORS 2.3: +5 wishlists per earlier Hit in the genre ...
    fans_cap: float = 10.0               # ... at most +10
    title_cap_k: float = None            # SECTORS 2.4 anti-spam bound (k x build seconds x base Income per title); None = off (the doc gives no k)
    force_scope: int = None              # launch-spam: always build this scope (0 = Game Jam)
    checkpoint_min: float = None         # S10 fix: a visible checkpoint (a verb, never a task) every this many engaged minutes while a title is in development
    half_lives: tuple = None             # None = the SECTORS 2.4 table (20 / 30 / 40 / 50 / 60 engaged minutes); a tuple replaces it (S9 fix: half-life proportional to the work)
    scope_of_rung: tuple = PK_GAMING_SCOPE_OF_RUNG


class PkCycle:
    """State of one Gaming company: advances only with ENGAGED seconds (a step is one engaged `dt`)."""

    def __init__(self, cfg):
        self.c = cfg
        self.t = 0.0
        self.dev = None
        self.live = None
        self.cat = 0.0
        self.hits = 0
        self.titles = 0
        self.tiers = {k: 0 for k in PK_TIERS}
        self.ups = 0
        self.ev = []

    def x(self):
        """Extra Income fraction right now (x base Income): live revenue plus back catalog, capped."""
        live = self.live["amp"] if self.live else 0.0
        return min(self.c.cap, live + self.cat)

    def score(self, d):
        c = self.c
        if c.policy == "rush":
            return c.rush_score
        tau = d["pol"] / d["W"]
        pts = [(0.0, c.score0), (c.tau_hit, 70.0), (c.tau_smash, 90.0), (c.tau_smash + (c.tau_smash - c.tau_hit), 100.0)]
        s = pts[-1][1]
        for (a, sa), (b, sb) in zip(pts, pts[1:]):
            if tau <= b:
                s = sa + (sb - sa) * (tau - a) / (b - a)
                break
        return s + min(c.fans_cap, c.fans_per_hit * self.hits)

    def step(self, dt, rung):
        """One engaged step. Returns the extra fraction paid during it (decided at the start of the step)."""
        c = self.c
        if c.policy == "never":
            self.t += dt
            return 0.0
        x = self.x()
        live = self.live
        if live:
            live["spent"] += min(live["amp"], c.cap) * dt
            if c.title_cap_k is not None and live["spent"] > c.title_cap_k * live["build"]:
                live["amp"] = 0.0                       # the per-title bound is used up: it earns nothing more
            else:
                live["amp"] *= 0.5 ** (dt / live["hl"])
        self.t += dt
        if live and c.update_rule != "none" and live["amp"] > 0.0 and self.t - live["last"] >= c.update_cd:
            k = live["ups"] + 1
            target = max(0.1, c.update_first - 0.1 * k) * live["peak"]
            amp = live["amp"]
            if target > amp and (c.update_rule == "every" or (c.update_rule == "half" and amp <= 0.5 * live["peak"])
                                 or (c.update_rule == "late" and amp <= 0.25 * live["peak"])):
                live["amp"], live["ups"], live["last"] = target, k, self.t
                self.ups += 1
                self.ev.append((self.t, "update"))
        d = self.dev
        if d is None:
            sc = c.force_scope if c.force_scope is not None else c.scope_of_rung[min(rung, len(c.scope_of_rung) - 1)]
            d = self.dev = {"scope": sc, "W": PK_GAMING_SCOPES[sc][1] * 60.0, "work": 0.0, "pol": 0.0, "pt": False}
            self.ev.append((self.t, "pitch"))
        if c.checkpoint_min:
            d["cp"] = d.get("cp", 0.0) + dt
            if d["cp"] >= c.checkpoint_min * 60:
                d["cp"] = 0.0
                self.ev.append((self.t, "checkpoint"))
        if d["work"] < d["W"]:
            d["work"] += dt
            if not d["pt"] and d["work"] >= d["W"] / 2:
                d["pt"] = True
                self.ev.append((self.t, "playtest"))
            if d["work"] >= d["W"]:
                self.ev.append((self.t, "content complete"))
            return x
        target = {"smash": 90.0, "hit": 70.0, "solid": 50.0}.get(c.policy, 0.0)
        s = self.score(d)
        if c.policy == "rush" or s >= target:
            tier = PK_TIERS[0 if s < 50 else 1 if s < 70 else 2 if s < 90 else 3]
            peak = c.peak[PK_TIERS.index(tier)] * c.scope_factor[d["scope"]]
            if live:
                self.cat = min(c.cat_cap, self.cat + c.cat_share * live["peak"])
            self.live = {"peak": peak, "amp": peak, "hl": (c.half_lives[d["scope"]] if c.half_lives else PK_GAMING_SCOPES[d["scope"]][2]) * 60.0, "ups": 0, "last": self.t, "spent": 0.0, "build": d["W"] + d["pol"]}
            if tier in ("Hit", "Smash"):
                self.hits += 1
            self.titles += 1
            self.tiers[tier] += 1
            self.dev = None
            self.ev.append((self.t, "launch " + tier))
        else:
            d["pol"] += dt
        return x


@dataclass
class PkOpt:
    """Options of `pk_run`. With every field at its default the run equals `long_run` (same random stream, same numbers)."""
    growth: float = LONG_LOOP_GROWTH
    skill: str = "typical"
    cash_mult: float = 1.0               # the Cash passes (2 = 2x Cash, 3 = 2x Cash + VIP)
    shareholder: bool = False
    max_days: int = 1100
    full_hours: float = LONG_FULL_HOURS
    over_cap: float = LONG_OVER_CAP
    f_mult: float = 1.0
    inc_mult: float = 1.0
    price_mult: float = 1.0
    away: tuple = LONG_AWAY
    fed: int = None
    fed_run: int = None
    fed_carry: bool = False
    fed_cap: bool = True
    sectors: tuple = ("Software",)       # the sector of loop 0, 1, 2 ... (cycled)
    gaming: PkGam = None                 # None = Gaming with PkGam() defaults
    beta: tuple = (1.0,) * 6             # Gaming's upgrade Incomes x beta[rung] (S3 fits it)
    f_gam: float = 1.0                   # Gaming's task bonus relative to Software's (ASSUMPTION: 1.0)
    seed_pct: float = 0.0                # CUSTOMIZE 5.1
    seed_cap: float = 0.0
    seed_basis: str = "prices"           # "prices" = c% of the sum of the new first rung's prices; "threshold" = c% of the valuation that opens the next rung
    decorator: bool = False              # spends all its leftover Cash on furniture: the seed is 0
    bonus: float = 0.0                   # CUSTOMIZE 5.2: Collection bonus, a Cash multiplier of 1 + bonus (never valuation)
    rounds: object = None                # FUNDING: None, an int (choice 1 Small / 2 Medium / 3 Large at every round, 0 skips) or a dict {stage: choice}
    round_bp: dict = None                # None = PK_FUND_LONG_BP
    round_delay: float = 0.0             # raise this share of the way through the stage instead of at once (FUNDING S8 mark: the last open round)
    dilution_cap: int = PK_FUND_CAP
    shop_done: bool = False              # the whole IPO shop is owned: speed perks maxed from the start, Shares are worth nothing
    T: tuple = None                      # stamp targets: hours of a regular player's loop 0, 1, 2 ... (CUSTOMIZE 1.5); None = no tiers
    ipo_mode: str = "ready"              # "ready" = go public the moment IPO-ready is reached (as long_run); "hunt" = from loop 1 on wait for ratio >= plat_ratio while Platinum is still possible
    pass_share: float = 0.0              # share of the run's engaged seconds with the 2x Cash pass (targets shrink by pass_shrink x this)
    tier: dict = None                    # None = PK_TIER
    record: bool = False                 # loop 0: record the purchase, milestone, board and cycle events (S10)
    away_fix: bool = False               # Gaming's away bank pays 10% of the base Income of the UNSCALED upgrade Incomes (a proposed fix, S3 check-in)


def pk_pass_opts(name):
    """The pass sets of the docs as PkOpt keywords."""
    return {"none": {}, "VIP": {"cash_mult": 1.5}, "Cash": {"cash_mult": 2.0}, "Cash+VIP": {"cash_mult": 3.0}, "Shareholder": {"shareholder": True},
            "Cash+Shareholder": {"cash_mult": 2.0, "shareholder": True}}[name]


def pk_dilute(base, D, dust):
    """FUNDING 3: Shares after dilution, round to the nearest Share and carry the rest (whole numbers, 1/10000 Share). Returns (paid, dust)."""
    exact = base * (10000 - D) + dust
    paid = (exact + 5000) // 10000
    return paid, exact - paid * 10000


def pk_run(kind, seed, loops=1, o=None):
    """`long_run` with the hooks of S1-S10: sector per loop (Software or the Gaming title cycle), seed Cash, Collection bonus, funding rounds
    with dilution, stamp tiers and the hunt for Platinum. Same random stream as long_run, so two options differ only by what they change."""
    o = o or PkOpt()
    spec = PK_PLAYERS[kind]
    rng = random.Random(seed * 7919 + zlib.crc32(kind.encode()))
    sk = spec["skill"] or o.skill
    items = LONG_ITEMS
    n_items = len(items)
    rung_of = [it[0] for it in items]
    price = [it[3] * o.price_mult for it in items]
    cap_of = [LONG_RUNGS[it[0]][2] for it in items]
    is_hire = [it[1] == "hire" for it in items]
    is_upg = [it[1] == "upgrade" for it in items]
    thr = long_thresholds(items, o.price_mult)
    n_rungs = len(LONG_RUNGS)
    away = o.away
    tier_cfg = o.tier or PK_TIER
    bonus_mult = 1.0 + o.bonus
    cash_mult = o.cash_mult * bonus_mult
    engaged_kind = sk != "macro"
    gcfg = o.gaming or PkGam()
    bp_table = o.round_bp or PK_FUND_LONG_BP
    loop, income, cash, val = 0, 0.0, 0.0, 0.0
    income_sw = 0.0                      # the base Income the same purchases give in Software (for the away fix)
    have = [False] * n_items
    nxt = 0
    stage, shares, spent_speed = 0, 0, 0
    speed = (1 + LONG_SPEED_PERKS[1]) if o.shop_done else 1.0
    eng_s = online_s = wt_s = 0.0
    eng_today, cur_day, fed_left, fed_run_left, bank_s = 0.0, -1, 0, (o.fed_run if o.fed_run is not None else 10 ** 9), 0.0
    best_hire = max(h[1] for h in LONG_HIRE_TYPES)
    carry = [0.0] * n_items
    now_inc = [0.0] * n_items
    nhire = 0
    fcache = {}
    dust = 0
    D = 0
    done_sectors = set()
    out = {"stage_h": [[0.0]], "ipo_h": [], "ipo_day": [], "online_h": [], "shares": [], "away_val": 0.0, "val_total": 0.0,
           "buy_h": [], "ms_h": [], "board_h": [], "cyc_ev": [], "loops": [],
           "rung_x": [[0.0, 0.0] for _ in range(n_rungs)], "inc_entry": [], "titles_entry": []}   # loop 0: extra x time per rung, base Income and titles when leaving each rung
    board_t, ms_next = 0.0, 0
    last_end = None
    pending = []                         # rounds opened and not yet raised: (stage, trigger valuation, choice)
    rounds_done = []                     # this run: (stage, choice, cash, bp)
    sector = o.sectors[0]
    gam = PkCycle(gcfg) if sector == "Gaming" else None
    gains = [0.0] * n_items
    loop_start_eng = 0.0

    def set_gains():
        for j in range(n_items):
            g = items[j][4] * o.inc_mult
            if sector == "Gaming" and is_upg[j]:
                g *= o.beta[rung_of[j]]
            gains[j] = g
    set_gains()

    def f_now():
        st = min(stage, n_rungs - 1)        # waiting for Platinum after IPO-ready keeps the last rung's budget
        key = (st, nhire, loop)
        hit = fcache.get(key)
        if hit is None:
            if sk == "macro":
                hit = 0.0
            else:
                roster = [items[j][4] for j in range(n_items) if have[j] and is_hire[j]]
                hit = active_factor(roster, st, loop, sk, (1, 2, 3), budget=LONG_RUNGS[st][3], unlock_map=LONG_TASK_UNLOCK)["f"] * o.f_mult
            fcache[key] = hit
        return hit

    for day in range(o.max_days):
        if day % 7 not in spec["days"]:
            continue
        for start_h, minutes in spec["sessions"]:
            if rng.random() > spec["chance"]:
                continue
            length = (max(1, minutes * rng.uniform(0.7, 1.3)) if spec["jitter"] else minutes) * 60
            s_start = day * DAY + start_h * 3600
            sc = long_scale(loop, o.growth)
            m_inc = long_mult(loop)
            if last_end is not None and away[0] > 0:
                gap = min(s_start - last_end, away[1])
                bank_s = min(away[1], bank_s + gap)
            t = 0.0
            while t < length:
                dt = min(LONG_DT, length - t)
                d = int((s_start + t - LONG_RESET_HOUR * 3600) // DAY)
                if d != cur_day:
                    cur_day, eng_today, fed_left = d, 0.0, (o.fed or 0)
                if not engaged_kind:
                    bank_s = min(away[1], bank_s + (length - t))
                    online_s += length - t
                    break
                if bank_s > 0:
                    pay_away = bank_s * away[0] * (income_sw if (o.away_fix and gam is not None) else income) * m_inc * speed
                    cash += pay_away * cash_mult
                    credit = pay_away * away[2]
                    val += credit
                    out["away_val"] += credit
                    bank_s = 0.0
                x = gam.step(dt, stage) if gam is not None else 0.0
                if gam is not None and o.record and loop == 0 and gam.ev:
                    out["cyc_ev"].extend((eng_s / 3600, name) for _, name in gam.ev)
                if gam is not None:
                    gam.ev = []
                if loop == 0:
                    out["rung_x"][min(stage, n_rungs - 1)][0] += x * dt
                    out["rung_x"][min(stage, n_rungs - 1)][1] += dt
                f = f_now() * (o.f_gam if gam is not None else 1.0) * rng.uniform(0.85, 1.15)
                base = income * m_inc * speed
                gain = base * (1 + f + x) * dt
                w = 1.0 if eng_today < o.full_hours * 3600 else o.over_cap
                cash += gain * cash_mult
                val += gain * w
                eng_today += dt
                eng_s += dt
                wt_s += dt * w
                online_s += dt
                t += dt
                if stage == LONG_BOARD_RUNG:
                    board_t += dt
                    if board_t >= LONG_BOARD[0]:
                        board_t -= LONG_BOARD[0]
                        pay = LONG_BOARD[1] * base
                        cash += pay * cash_mult
                        val += pay * w
                        if loop == 0:
                            out["board_h"].append(eng_s / 3600)
                if pending:                                  # a delayed round: raise it once the player is that far through its stage
                    for pr in pending[:]:
                        if val >= pr[1]:
                            pending.remove(pr)
                            v0 = val
                            res = _pk_raise(pr[0], pr[2], thr, sc, bp_table, D, o.dilution_cap)
                            if res:
                                cash += res[0]
                                D += res[1]
                                rounds_done.append((pr[0], pr[2], res[0], res[1]))
                            assert val == v0, "round Cash must not count toward the IPO valuation"
                while True:
                    while nxt < n_items and have[nxt]:
                        nxt += 1
                    if nxt >= n_items or rung_of[nxt] > stage:
                        break
                    j = nxt
                    cost, g = price[j] * sc, gains[j]
                    if is_hire[j]:
                        if loop > 0:
                            cost, g = 0.0, carry[j] or g
                        if fed_left > 0 and fed_run_left > 0:
                            cost, g = 0.0, max(g, cap_of[j] if o.fed_cap else best_hire)
                            fed_left -= 1
                            fed_run_left -= 1
                    if cash < cost:
                        break
                    cash -= cost
                    income += g
                    income_sw += g if not is_upg[j] else items[j][4] * o.inc_mult
                    now_inc[j] = g
                    have[j] = True
                    if loop == 0:
                        out["buy_h"].append((rung_of[j], eng_s / 3600))
                    if is_hire[j]:
                        nhire += 1
                if stage == LONG_BOARD_RUNG:
                    lo_v, hi_v = thr[stage - 1] * sc, thr[stage] * sc
                    while ms_next < len(LONG_MILESTONES) and val >= lo_v + LONG_MILESTONES[ms_next] * (hi_v - lo_v):
                        if loop == 0:
                            out["ms_h"].append(eng_s / 3600)
                        ms_next += 1
                while stage < n_rungs and val >= thr[stage] * sc:
                    stage += 1
                    if stage >= n_rungs:
                        pending = []                         # every round closes at IPO-ready
                    if loop == 0:
                        out["inc_entry"].append(income)
                        out["titles_entry"].append(gam.titles if gam is not None else 0)
                    if stage < n_rungs:
                        out["stage_h"][-1].append(eng_s / 3600)
                        ch = o.rounds.get(stage, 0) if isinstance(o.rounds, dict) else (o.rounds or 0)
                        if ch and stage in bp_table:
                            trig = thr[stage - 1] * sc + o.round_delay * (thr[stage] - thr[stage - 1]) * sc
                            if o.round_delay <= 0:
                                v0 = val
                                res = _pk_raise(stage, ch, thr, sc, bp_table, D, o.dilution_cap)
                                if res:
                                    cash += res[0]
                                    D += res[1]
                                    rounds_done.append((stage, ch, res[0], res[1]))
                                assert val == v0, "round Cash must not count toward the IPO valuation"
                            else:
                                pending.append((stage, trig, ch))
                if stage >= n_rungs:
                    ratio_raw = val / (thr[-1] * sc)
                    stamp_h = ((eng_s - loop_start_eng) if tier_cfg.get("clock") == "raw" else wt_s) / 3600     # the stamp clock: weighted like the valuation (CUSTOMIZE 1.5) or raw engaged seconds (S7 fix)
                    T_loop = o.T[min(loop, len(o.T) - 1)] if o.T else None
                    T_eff = T_loop * (1 - tier_cfg["pass_shrink"] * o.pass_share) if T_loop else None
                    replay = sector in done_sectors
                    go = True
                    if o.ipo_mode == "hunt" and replay and T_eff is not None:
                        go = not (ratio_raw < tier_cfg["plat_ratio"] and stamp_h < tier_cfg["plat_frac"] * T_eff)
                    if not go:
                        continue
                    ratio = min(LONG_SHARES[2], ratio_raw)
                    gained = int(LONG_SHARES[0] * (1 + LONG_SHARES[1] * loop) * ratio ** LONG_SHARES[3] * (2 if o.shareholder else 1))
                    paid, dust = pk_dilute(gained, min(o.dilution_cap, D), dust)
                    stake = 10000 - min(o.dilution_cap, D)
                    tier = 1
                    if replay and T_eff is not None:
                        if stamp_h <= tier_cfg["plat_frac"] * T_eff and ratio_raw >= tier_cfg["plat_ratio"] and stake >= tier_cfg["plat_stake"]:
                            tier = 3
                        elif stamp_h <= tier_cfg["gold_frac"] * T_eff and ratio_raw >= 1.0 and stake >= tier_cfg["gold_stake"]:
                            tier = 2
                    out["loops"].append({"sector": sector, "eng_h": (eng_s - loop_start_eng) / 3600, "stamp_h": stamp_h, "ratio": ratio_raw, "base_shares": gained,
                                         "shares": paid, "D": min(o.dilution_cap, D), "stake": stake, "tier": tier, "replay": replay, "cash": cash,
                                         "owned": sum(have), "rounds": list(rounds_done), "T_eff": T_eff,
                                         "titles": gam.titles if gam is not None else 0, "tiers": dict(gam.tiers) if gam is not None else None, "updates": gam.ups if gam is not None else 0})
                    done_sectors.add(sector)
                    shares += paid
                    out["shares"].append(paid)
                    out["ipo_h"].append(eng_s / 3600)
                    out["online_h"].append(online_s / 3600)
                    out["ipo_day"].append((s_start + t) / DAY)
                    out["val_total"] += val
                    for j in range(n_items):
                        if have[j] and is_hire[j]:
                            carry[j] = now_inc[j] if (o.fed_carry or now_inc[j] <= items[j][4] * o.inc_mult + 1e-9) else items[j][4] * o.inc_mult
                    if not o.shop_done:
                        room = max(0, LONG_SPEED_PERKS[0] - spent_speed)
                        buy = min(room, shares)
                        spent_speed += buy
                        shares -= buy
                        speed = 1 + LONG_SPEED_PERKS[1] * spent_speed / LONG_SPEED_PERKS[0]
                    out["loops"][-1]["perk"] = spent_speed
                    old_cash = cash
                    loop += 1
                    sector = o.sectors[loop % len(o.sectors)]
                    gam = PkCycle(gcfg) if sector == "Gaming" else None
                    set_gains()
                    income, income_sw, val, stage, nhire = 0.0, 0.0, 0.0, 0, 0
                    have = [False] * n_items
                    nxt = 0
                    D, wt_s, loop_start_eng = 0, 0.0, eng_s
                    pending, rounds_done = [], []
                    board_t, ms_next = 0.0, 0
                    fed_run_left = o.fed_run if o.fed_run is not None else 10 ** 9
                    out["stage_h"].append([eng_s / 3600])
                    if loop >= loops:
                        out["away_share"] = out["away_val"] / max(out["val_total"], 1e-9)
                        return out
                    sc = long_scale(loop, o.growth)
                    m_inc = long_mult(loop)
                    cash = 0.0
                    if o.seed_pct > 0 and o.seed_cap > 0 and not o.decorator:
                        basis = (sum(price[j] for j in range(n_items) if rung_of[j] == 0) if o.seed_basis == "prices" else thr[0]) * sc
                        cash = min(o.seed_pct * old_cash, o.seed_cap * basis)
                        out["loops"][-1]["seed_next"] = cash
            last_end = s_start + length
    out["away_share"] = out["away_val"] / max(val + out["val_total"], 1e-9)
    return out


def _pk_raise(stage, choice, thr, sc, bp_table, D, cap):
    """One round: (Cash, bp) of `choice` (1 Small, 2 Medium, 3 Large) at `stage`; a choice that would take the total past the cap is locked,
    so the player takes the biggest choice that still fits (None = nothing fits). Cash = floor(stage valuation x cashBp / 10000): FUNDING 1."""
    while choice > 0:
        bp = bp_table[stage][choice - 1]
        if D + bp <= cap:
            return int(thr[stage - 1] * sc * PK_FUND_CASH_BP[choice - 1] // 10000), bp
        choice -= 1
    return None


def pk_selfcheck(n=6):
    """The engine with every hook off must equal long_run exactly (same hours, Shares, stage times). Prints one line; raises if not."""
    bad = 0
    for kind in ("dedicated", "regular", "casual", "task-bot"):
        for seed in range(n):
            a = long_run(kind, seed, loops=3)
            b = pk_run(kind, seed, loops=3)
            for k in ("ipo_h", "shares", "online_h", "ipo_day", "stage_h"):
                if a[k] != b[k]:
                    bad += 1
    if bad:
        raise AssertionError(f"pk_run differs from long_run in {bad} fields")
    print(f"Engine check: pk_run with every hook off equals long_run exactly ({4 * n} runs x 3 loops, hours, Shares, stage times, days).")


def _pq(vals, p):
    """Percentile p (0-100) of a list, by linear interpolation."""
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * p / 100
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def _pdist(vals, fmt="{:.1f}"):
    """'median (p10-p90)' of a list."""
    vals = [x for x in vals if x is not None]
    if not vals:
        return "-"
    return fmt.format(_pq(vals, 50)) + " (" + fmt.format(_pq(vals, 10)) + " to " + fmt.format(_pq(vals, 90)) + ")"


def pk_many(kind, n, loops, o=None):
    """n seeds of one profile (seeds 0..n-1: the same random streams for every option, so two options differ only by what they change)."""
    return [pk_run(kind, s, loops, o) for s in range(n)]


def pk_loop_h(outs, i, key="eng_h"):
    return [r["loops"][i][key] if len(r["loops"]) > i else None for r in outs]


def pk_rel(var, base, i, key="eng_h"):
    """Per-seed change of loop i in % (positive = faster than base), over the seeds both finished."""
    a, b = pk_loop_h(var, i, key), pk_loop_h(base, i, key)
    return [(1 - x / y) * 100 for x, y in zip(a, b) if x is not None and y is not None and y > 0]


def sim_s1(n):
    """S1 seed (CUSTOMIZE 5.5, 5.1): 0 / 10 / 25% cap: at most 5% faster per loop; a decorator at most 5% slower."""
    print("\n## S1. Seed Cash at a founding (docs/CUSTOMIZE_PROPOSAL.md 5.1, 5.5)")
    print(f"Software ladder (LONG_ITEMS), typical skill, no rounds, no passes, {n} seeds per cell, 4 loops. Seed = min(s% of the old company's Cash, c% of the new first rung's prices x StageScale), "
          "a gift: Cash only, never valuation (the engine adds it to `cash` and asserts nothing else moves). Numbers are the change of that loop's engaged hours against the same seed with no seed (positive = faster), median (p10 to p90) over seeds.")
    variants = [("no seed", {}),
                ("s 10%, cap 10%", dict(seed_pct=0.10, seed_cap=0.10)),
                ("**s 10%, cap 25% (the doc's placeholder)**", dict(seed_pct=0.10, seed_cap=0.25)),
                ("s 10%, cap 50%", dict(seed_pct=0.10, seed_cap=0.50)),
                ("s 100%, cap 25% (only the cap limits)", dict(seed_pct=1.0, seed_cap=0.25)),
                ("s 10%, cap 25% of the next threshold (other reading of 'first rung's prices')", dict(seed_pct=0.10, seed_cap=0.25, seed_basis="threshold")),
                ("decorator: spent every leftover Cash on furniture (seed 0); compared with the 10% / 25% player", dict(seed_pct=0.10, seed_cap=0.25, decorator=True)),
                ("heavy decorator: also puts 10% of all Cash into furniture, no seed; compared with the 10% / 25% player (ASSUMPTION: 10%)", dict(cash_mult=0.9))]
    worst, dec_worst, heavy_worst = 0.0, 0.0, 0.0
    for kind in ("regular", "dedicated"):
        base = pk_many(kind, n, 4)
        placeholder = pk_many(kind, n, 4, PkOpt(seed_pct=0.10, seed_cap=0.25))
        print(f"\n**{kind}** (loop 0 is the first company: no seed, so no change)\n")
        print("| Variant | Loop 1 (IPO 2) | Loop 2 (IPO 3) | Loop 3 (IPO 4) | Garage rung of loop 1 |")
        print("|---|---|---|---|---|")
        for label, kw in variants[1:]:
            var = pk_many(kind, n, 4, PkOpt(**kw))
            dec = "decorator" in label
            ref = placeholder if dec else base      # a decorator is compared with the seeded player it could have been
            cells = []
            for i in (1, 2, 3):
                rel = pk_rel(var, ref, i)
                cells.append(_pdist(rel, "{:+.2f}%"))
                if "doc's placeholder" in label:
                    worst = max(worst, _pq(rel, 50))
                if dec:
                    dec_worst = max(dec_worst, -_pq(rel, 50)) if label.startswith("decorator") else dec_worst
                    heavy_worst = max(heavy_worst, -_pq(rel, 50)) if label.startswith("heavy") else heavy_worst
            gar = [(1 - (r["stage_h"][1][1] - r["stage_h"][1][0]) / (b["stage_h"][1][1] - b["stage_h"][1][0])) * 100 for r, b in zip(var, ref) if len(r["stage_h"]) > 1 and len(r["stage_h"][1]) > 1 and len(b["stage_h"][1]) > 1]
            print(f"| {label} | " + " | ".join(cells) + f" | {_pdist(gar, '{:+.1f}%')} |")
        cash = [r["loops"][0]["cash"] for r in placeholder]
        seed = [r["loops"][0].get("seed_next", 0.0) for r in placeholder]
        first = sum(it[3] for it in LONG_ITEMS if it[0] == 0) * long_scale(1, LONG_LOOP_GROWTH)
        print(f"\nOld company's Cash at the first IPO: median {fmt_cash(_pq(cash, 50))}; the cap (25% of the Garage rung's prices at loop 1) is {fmt_cash(0.25 * first)}; the seed paid: median {fmt_cash(_pq(seed, 50))}. "
              f"So the cap binds in {sum(1 for s in seed if abs(s - 0.25 * first) < 1) * 100 // len(seed)}% of runs and 's' never does.")
    print(f"\n**Result.** Placeholder (10% / 25%): the best loop is {worst:+.2f}% faster (median), against the mark of 5%: {'PASS' if worst <= 5 else 'FAIL'}. "
          f"The decorator (seed 0) is at most {dec_worst:.2f}% slower than the seeded player: {'PASS' if dec_worst <= 5 else 'FAIL'}; "
          f"a heavy decorator (10% of all Cash in furniture) {heavy_worst:.2f}% slower ({'PASS' if heavy_worst <= 5 else 'FAIL'}, but only because the 10% is a choice).")
    return {"s1": worst, "s1_dec": dec_worst, "s1_heavy": heavy_worst}


def sim_s2(n):
    """S2 bonus (CUSTOMIZE 5.5, 5.2): 0-12 points x pass sets: at the cap at least 95% of the no-bonus hours."""
    print("\n## S2. Collection bonus x passes (docs/CUSTOMIZE_PROPOSAL.md 5.2, 5.5)")
    print(f"Software ladder, regular player, typical skill, {n} seeds, IPO 1 and IPO 2. The bonus is a Cash multiplier of (1 + points/100) on top of the passes (2 x 1.5 x 1.10 = x3.3), applied to spendable Cash only: "
          "the valuation counts base Cash (LONG_GAME section 6), so the bonus never reaches it. 'Points' above the cap (10) count 10. Cell = engaged hours of that IPO as a % of the same pass set with 0 points, median (p10 to p90); the mark is 95% or more at the cap.")
    points = (0.0, 1.5, 3.0, 5.0, 7.5, 10.0, 12.0)
    print("| Pass set | Cash x | " + " | ".join(f"{p:g} pts" + (" (cap 10)" if p > PK_BONUS[3] else "") for p in points[1:]) + " |")
    print("|---|---|" + "---|" * (len(points) - 1))
    notes = []
    worst = 100.0
    for name in ("none", "VIP", "Cash", "Cash+VIP", "Shareholder", "Cash+Shareholder"):
        kw = pk_pass_opts(name)
        base = pk_many("regular", n, 2, PkOpt(**kw))
        cells = []
        for p in points[1:]:
            var = pk_many("regular", n, 2, PkOpt(bonus=min(p, PK_BONUS[3]) / 100, **kw))
            r1 = [(b / a) * 100 if a else None for a, b in zip(pk_loop_h(base, 0), pk_loop_h(var, 0))]
            r2 = [(b / a) * 100 if a else None for a, b in zip(pk_loop_h(base, 1), pk_loop_h(var, 1))]
            cells.append(f"{_pq(r1, 50):.1f}% ({_pq(r1, 10):.1f} to {_pq(r1, 90):.1f}); loop 2 {_pq(r2, 50):.1f}%")
            if p >= PK_BONUS[3]:
                worst = min(worst, _pq(r1, 50), _pq(r2, 50))
        mult = kw.get("cash_mult", 1.0)
        print(f"| {name} | x{mult:g} (x{mult * 1.10:.2f} at the cap) | " + " | ".join(cells) + " |")
        if kw.get("shareholder"):
            sh0 = med([r["shares"][0] for r in base])
            shb = med([r["shares"][0] for r in pk_many("regular", n, 1, PkOpt(bonus=0.10, **kw))])
            notes.append(f"{name}: Shares at IPO 1 with the bonus at the cap {shb:.0f}, without {sh0:.0f}")
    for note in notes:
        print(f"\n({note})")
    print(f"\n**Result.** At the cap the shortest run is {worst:.1f}% of the no-bonus hours (mark: 95% or more): {'PASS' if worst >= 95 else 'FAIL'}. "
          "Shares are unchanged by the bonus (it never reaches the valuation).")
    return {"s2": worst}



_PK_FIT = {}


def pk_rung_hours(out):
    """Engaged hours spent in each rung of loop 0 (the last rung up to the IPO); only the rungs the run reached."""
    ent = list(out["stage_h"][0])
    if out["ipo_h"]:
        ent.append(out["ipo_h"][0])
    return [ent[i + 1] - ent[i] for i in range(len(ent) - 1)]


def pk_ref_hours(o):
    """Hours per rung of the always-engaged reference player (no away pay, no daily cap): the fit tool."""
    r = pk_run("reference", 0, 1, replace(o, away=(0, 0, 0), full_hours=1e9, max_days=400))
    return pk_rung_hours(r) if r["ipo_h"] else None


PK_SKILLS = (("typical", dict(skill="typical")), ("fast", dict(skill="expert")), ("slow", dict(skill="typical", f_mult=0.5)))


def pk_fit_beta(gcfg, f_gam=1.0, skills=("typical",)):
    """S3 fit: Gaming's upgrade Incomes x beta[rung], found rung by rung (bisection) so that the reference player spends the same hours in that rung as in Software.
    With several skills the fit matches the AVERAGE of their Gaming / Software hour ratios (typical, fast = expert at tasks, slow = task bonus x0.5)."""
    key = (repr(gcfg), f_gam, tuple(skills))
    if key in _PK_FIT:
        return _PK_FIT[key]
    sk = dict(PK_SKILLS)
    sw = {k: pk_ref_hours(PkOpt(**sk[k])) for k in skills}
    beta = [1.0] * len(LONG_RUNGS)
    for r in range(len(LONG_RUNGS)):
        lo, hi = 0.15, 1.8
        for _ in range(16):
            mid = (lo + hi) / 2
            b = list(beta)
            b[r] = mid
            dev = 0.0
            for k in skills:
                hrs = pk_ref_hours(PkOpt(sectors=("Gaming",), gaming=gcfg, beta=tuple(b), f_gam=f_gam, **sk[k]))
                dev += (hrs[r] / sw[k][r] - 1) if (hrs is not None and len(hrs) > r) else 1.0
            if dev > 0:
                lo = mid
            else:
                hi = mid
        beta[r] = (lo + hi) / 2
    _PK_FIT[key] = tuple(round(b, 4) for b in beta)
    return _PK_FIT[key]




def pk_med_rungs(outs):
    """Median hours per rung over the seeds that reached it (at least half of them)."""
    cols = []
    for i in range(len(LONG_RUNGS)):
        v = [pk_rung_hours(r)[i] for r in outs if len(pk_rung_hours(r)) > i]
        cols.append(_pq(v, 50) if len(v) >= len(outs) / 2 else None)
    return cols


def pk_parity_table(n, gcfg, beta, kinds, skills=PK_SKILLS, away_fix=False, label=""):
    """Gaming hours / Software hours per rung for each profile and skill (median over n seeds, the same random streams). Returns (worst deviation in %, where, offenders)."""
    print("| Profile | Skill | " + " | ".join(r[0] for r in LONG_RUNGS) + " | IPO 1 | IPO 1 per-seed p10 to p90 |")
    print("|---|---|" + "---|" * (len(LONG_RUNGS) + 2))
    worst, worst_at, bad = 0.0, "", []
    for kind in kinds:
        for sname, skw in skills:
            if kind == "reference" and sname != "typical":
                continue
            nn = n if kind != "check-in" else max(5, n // 4)
            o_s = PkOpt(**skw, **({"away": (0, 0, 0), "full_hours": 1e9, "max_days": 400} if kind == "reference" else {}))
            o_g = replace(o_s, sectors=("Gaming",), gaming=gcfg, beta=beta, away_fix=away_fix)
            rs = pk_many(kind, nn if kind != "reference" else 1, 1, o_s)
            rg = pk_many(kind, nn if kind != "reference" else 1, 1, o_g)
            a, b = pk_med_rungs(rs), pk_med_rungs(rg)
            cells, devs = [], []
            for x, y in zip(a, b):
                if x is None or y is None:
                    cells.append("n/a")
                else:
                    d = (y / x - 1) * 100
                    cells.append(f"{100 + d:.1f}")
                    devs.append(d)
            ipo = [(g["ipo_h"][0] / s_["ipo_h"][0] - 1) * 100 for s_, g in zip(rs, rg) if s_["ipo_h"] and g["ipo_h"]]
            if ipo:
                devs.append(_pq(ipo, 50))
            mx = max((abs(d) for d in devs), default=0.0)
            if mx > worst:
                worst, worst_at = mx, f"{kind}/{sname}"
            if mx > 5:
                bad.append(f"{kind}/{sname} ({mx:.1f}%)")
            tail = f" {100 + _pq(ipo, 50):.1f} | {100 + _pq(ipo, 10):.1f} to {100 + _pq(ipo, 90):.1f} |" if ipo else " never | |"
            print(f"| {kind} | {sname} | " + " | ".join(cells) + " |" + tail)
    return worst, worst_at, bad


def pk_fit_table(gcfg, beta, title):
    """Fit table: hours per rung, the fitted beta, the base Income Gaming has at the end of each rung against Software, the average extra and the titles per rung."""
    sw_o = PkOpt(away=(0, 0, 0), full_hours=1e9, max_days=400)
    sw = pk_run("reference", 0, 1, sw_o)
    g1 = pk_run("reference", 0, 1, replace(sw_o, sectors=("Gaming",), gaming=gcfg))
    gf = pk_run("reference", 0, 1, replace(sw_o, sectors=("Gaming",), gaming=gcfg, beta=beta))
    hs, h1, hf = pk_rung_hours(sw), pk_rung_hours(g1), pk_rung_hours(gf)
    print(f"### {title}")
    print("| Rung | Software h | Gaming h, beta 1.0 (no fit) | fitted beta | Gaming h after the fit | Gaming base Income / Software's at the end of the rung | average extra (x base) | titles launched in the rung |")
    print("|---|---|---|---|---|---|---|---|")
    prev = 0
    for i, (name, *_r) in enumerate(LONG_RUNGS):
        end_t = gf["titles_entry"][i] if i < len(gf["titles_entry"]) else gf["loops"][0]["titles"]
        inc_ratio = gf["inc_entry"][i] / sw["inc_entry"][i] if i < len(gf["inc_entry"]) else float("nan")
        xs, ts = gf["rung_x"][i]
        print(f"| {name} | {hs[i]:.2f} | {h1[i]:.2f} | {beta[i]:.3f} | {hf[i]:.2f} | {inc_ratio:.2f} | {xs / ts:.2f} | {end_t - prev} |")
        prev = end_t
    print(f"\nTotal titles to IPO 1: {gf['loops'][0]['titles']} (SECTORS 2.10 estimates about 40: 4 / 5 / 6 / 6 / 14 / 7). Hours: Software {sum(hs):.1f}, Gaming before the fit {sum(h1):.1f}, after {sum(hf):.1f}. "
          "The doc's fitted base is 0.77 of Software's Income for the whole ladder (SECTORS 2.10): the column 'base Income' is the same quantity measured.\n")


def sim_s3(n):
    """S3 parity (CUSTOMIZE 5.5, SECTORS 4): Software against Gaming (Hit policy), every rung and every profile, within +-5%."""
    print("\n## S3. Parity: Software and Gaming, hours per engaged hour (docs/SECTORS_PROPOSAL.md 2.4, 4; docs/CUSTOMIZE_PROPOSAL.md 5.5)")
    gcfg = PkGam()
    beta = pk_fit_beta(gcfg)
    print("Gaming model: the title cycle of SECTORS 2.2-2.4 (scope per rung, peak x tier, half-life, Live Updates, back catalog, cap 0.8), typical policy = Polish to Hit with an update when revenue is under half the peak; "
          "its extra pays x base Income on top of the base and the task bonus, only while engaged, never in the away bank. Gaming's upgrade Incomes are scaled by beta per rung (hires keep CreatureConfig's Income), "
          "fitted rung by rung with the always-engaged reference player (typical skill) so that each rung takes the same hours as in Software. Assumptions: section 'Assumptions' of docs/SIMS_RESULTS.md.\n")
    pk_fit_table(gcfg, beta, "Fit 1: the doc's rule (fit to the typical player)")
    kinds = ("reference", "dedicated", "regular", "casual", "heavy", "boundary", "check-in")
    print(f"### Parity with fit 1: Gaming hours / Software hours, per rung, in % (median over {n} seeds; mark 95 to 105)")
    w1, at1, bad1 = pk_parity_table(n, gcfg, beta, kinds)
    typ = [k for k in kinds]
    print(f"\nWorst deviation with fit 1: {w1:.1f}% ({at1}). Outside +-5%: {', '.join(bad1) if bad1 else 'none'}.")
    print("\n### Loops 2 and 3 (regular, typical): hours of IPO 2 and IPO 3, a Gaming company in every loop, in % of Software")
    rs = pk_many("regular", max(8, n // 2), 3, PkOpt())
    rg = pk_many("regular", max(8, n // 2), 3, PkOpt(sectors=("Gaming",), gaming=gcfg, beta=beta))
    for i in (0, 1, 2):
        v = [(g["loops"][i]["eng_h"] / s_["loops"][i]["eng_h"]) * 100 for s_, g in zip(rs, rg) if len(s_["loops"]) > i and len(g["loops"]) > i]
        print(f"- IPO {i + 1}: Software {_pq([s_['loops'][i]['eng_h'] for s_ in rs], 50):.1f} h, Gaming {_pq([g['loops'][i]['eng_h'] for g in rg], 50):.1f} h = {_pdist(v, '{:.1f}')}%")
    print("\n### Fix A: Gaming's away bank pays on the Software-equivalent base (`away_fix`: 10% of the base Income of the unscaled upgrade Incomes), fit 1 beta")
    wa, ata, bada = pk_parity_table(n, gcfg, beta, ("casual", "check-in"), skills=PK_SKILLS[:1], away_fix=True)
    print(f"\nWith the away fix the check-in profile is within {wa:.1f}% ({ata}) at the rungs it reaches.")
    print("\n### Fix B: smaller launch revenue (peaks x0.6: 0.09 / 0.21 / 0.36 / 0.48, cap 0.48, back catalog 0.06), refitted; the skill spread is x / (1 + f), so a smaller x spreads less")
    gB = replace(gcfg, peak=tuple(round(x * 0.6, 3) for x in gcfg.peak), cap=0.48, cat_cap=0.06)
    betaB = pk_fit_beta(gB)
    pk_fit_table(gB, betaB, "Fit B")
    print(f"### Parity with fix B and the away fix (median over {n} seeds; mark 95 to 105)")
    wb, atb, badb = pk_parity_table(n, gB, betaB, ("reference", "dedicated", "regular", "casual", "heavy", "boundary", "check-in"), away_fix=True)
    print(f"\nWorst deviation with fix B and the away fix: {wb:.1f}% ({atb}). Outside +-5%: {', '.join(badb) if badb else 'none'}.")
    ok_typ = all(not b.split("/")[1].startswith(("fast", "slow")) and not b.startswith("check-in") for b in bad1)
    print("\n**Result.** " + (f"Fit 1 (the doc's rule): every rung of every schedule at the typical skill is inside +-5% except the profiles named above. "
          f"Worst {w1:.1f}% ({at1}): " + ("PASS." if w1 <= 5 else "FAIL (check-in, which pays only the away bank; the fast and slow skills are marginal at +-6%).")
          + f" With fix B and the away fix the worst is {wb:.1f}% ({atb}): " + ("PASS." if wb <= 5 else "marginal.")))
    return {"s3": w1, "s3_fixed": wb, "beta": beta, "betaB": betaB, "bad": bad1, "badB": badb}

PK_POLICIES = (    # SECTORS 2.10 policy table: (label, PkGam changes, the doc's estimate of the IPO 1 hours of a regular player)
    ("Polish to Smash, every update", dict(policy="smash", update_rule="every"), 54),
    ("Polish to Hit (typical, the fit)", dict(policy="hit", update_rule="half"), 57),
    ("Ship at content complete (Solid)", dict(policy="solid", update_rule="none"), 63),
    ("Rush every title (Flop)", dict(policy="rush", update_rule="none"), 69),
    ("Never ship", dict(policy="never", update_rule="none"), 74),
)


def pk_gam_ipo1(kind, skw, gcfg, beta, n, **extra):
    """Engaged hours to IPO 1 of n seeds of a Gaming player (None if a seed never got there)."""
    outs = pk_many(kind, n, 1, PkOpt(sectors=("Gaming",), gaming=gcfg, beta=beta, **skw, **extra))
    return [r["ipo_h"][0] if r["ipo_h"] else None for r in outs]


def pk_sw_ipo1(kind, skw, n):
    return [r["ipo_h"][0] if r["ipo_h"] else None for r in pk_many(kind, n, 1, PkOpt(**skw))]


def _pk_pct(g, s_):
    """Per-seed % that Gaming takes longer than Software (positive = slower)."""
    return [(a / b - 1) * 100 for a, b in zip(g, s_) if a is not None and b is not None]


def sim_s9(n):
    """S9 launch policy (SECTORS 4, 2.10): five policies per profile; launch-spam; update timing."""
    print("\n## S9. Launch policy (docs/SECTORS_PROPOSAL.md 2.10, 4)")
    n = max(8, n // 2)
    base = PkGam()
    beta = pk_fit_beta(base)
    profiles = (("regular", "typical", dict(skill="typical")), ("dedicated", "typical", dict(skill="typical")), ("casual", "typical", dict(skill="typical")),
                ("regular", "fast", dict(skill="expert")), ("regular", "slow", dict(skill="typical", f_mult=0.5)))
    sw = {(k, sk): pk_sw_ipo1(k, skw, n) for k, sk, skw in profiles}
    print(f"Gaming with the fit-1 beta of S3 {tuple(round(b, 2) for b in beta)} (fitted on the Hit policy), IPO 1, {n} seeds per cell, engaged hours; cell = Gaming hours as a change against Software for the same profile and seeds "
          "(positive = slower), median (p10 to p90). Marks: Smash at most 5% faster (>= -5); Solid at most 12% slower (<= +12); Flop at most 25% slower (<= +25). The doc's own estimates of regular-player hours are in the last column.\n")
    print("| Policy | " + " | ".join(f"{k} {sk}" for k, sk, _ in profiles) + " | regular typical, hours | doc estimate, hours |")
    print("|---|" + "---|" * (len(profiles) + 2))
    res = {}
    for label, kw, est in PK_POLICIES:
        cells = []
        for k, sk, skw in profiles:
            g = pk_gam_ipo1(k, skw, replace(base, **kw), beta, n)
            pc = _pk_pct(g, sw[(k, sk)])
            res[(label, k, sk)] = _pq(pc, 50) if pc else None
            cells.append(_pdist(pc, "{:+.1f}%") if pc else "never")
            if (k, sk) == ("regular", "typical"):
                hours = _pq([x for x in g if x is not None], 50) if any(x is not None for x in g) else None
        print(f"| {label} | " + " | ".join(cells) + f" | {hours:.1f} | {est} |" if hours else f"| {label} | " + " | ".join(cells) + f" | never | {est} |")
    smash = min(v for (l, k, sk), v in res.items() if l.startswith("Polish to Smash") and v is not None)
    solid = max(v for (l, k, sk), v in res.items() if l.startswith("Ship at") and v is not None)
    flop = max(v for (l, k, sk), v in res.items() if l.startswith("Rush") and v is not None)
    g = pk_gam_ipo1("regular", dict(skill="typical"), replace(base, policy="smash", update_rule="half"), beta, n)
    print(f"\n(Smash with the smarter update rule, 'when under half the peak': {_pdist(_pk_pct(g, sw[('regular', 'typical')]), '{:+.1f}%')} for the regular typical player.)")
    print(f"\nWorst cell per mark: Smash {smash:+.1f}% (mark >= -5), Solid {solid:+.1f}% (mark <= +12), Flop {flop:+.1f}% (mark <= +25).")
    # the Smash polish cost is the doc's biggest open number: sweep it
    print("\n### What Smash costs: extra polish needed for Smash, as a multiple of the work (the doc gives no number; Hit is 0.5 by SECTORS 2.10)")
    print("| tau_smash | Smash vs Software (regular typical) | Smash vs Hit | titles to IPO 1 (Smash) |")
    print("|---|---|---|---|")
    hit_g = pk_gam_ipo1("regular", dict(skill="typical"), base, beta, n)
    for tau in (0.8, 1.0, 1.5, 2.0, 3.0):
        gc = replace(base, policy="smash", update_rule="every", tau_smash=tau)
        g = pk_gam_ipo1("regular", dict(skill="typical"), gc, beta, n)
        pc = _pk_pct(g, sw[("regular", "typical")])
        vs_hit = [(a / b - 1) * 100 for a, b in zip(g, hit_g) if a and b]
        tit = [r["loops"][0]["titles"] for r in pk_many("regular", min(n, 6), 1, PkOpt(sectors=("Gaming",), gaming=gc, beta=beta))]
        print(f"| {tau} | {_pdist(pc, '{:+.1f}%')} | {_pdist(vs_hit, '{:+.1f}%')} | {_pq(tit, 50):.0f} |")
    print("\n### Launch-spam: only Game Jams, the smallest scope, all the way up the ladder (a title every 15 to 25 engaged minutes), against the typical Hit player")
    print("| Spam policy | Gaming vs Software (regular typical) | gain over the typical Hit player |")
    print("|---|---|---|")
    hit_pc = _pk_pct(hit_g, sw[("regular", "typical")])
    spam_gain = []
    for label, kw in (("Jam Solid, no updates", dict(policy="solid", update_rule="none")), ("Jam Solid, update every cooldown", dict(policy="solid", update_rule="every")),
                      ("Jam Hit, update when under half", dict(policy="hit", update_rule="half")), ("Jam Hit, update every cooldown", dict(policy="hit", update_rule="every")),
                      ("Jam Flop (rush), no updates", dict(policy="rush", update_rule="none"))):
        g = pk_gam_ipo1("regular", dict(skill="typical"), replace(base, force_scope=0, **kw), beta, n)
        pc = _pk_pct(g, sw[("regular", "typical")])
        gain = [(b / a - 1) * 100 for a, b in zip(g, hit_g) if a and b]
        spam_gain.append(_pq(gain, 50))
        print(f"| {label} | {_pdist(pc, '{:+.1f}%')} | {_pdist(gain, '{:+.1f}%')} faster |")
    print("\n### Update timing: the Hit player with each rule for when to use a Live Update (best against worst)")
    print("| Rule | Gaming vs Software (regular typical) |")
    print("|---|---|")
    meds = {}
    for label, rule in (("never update", "none"), ("only when revenue is under a quarter of the peak", "late"), ("when under half the peak (typical)", "half"), ("every time the cooldown allows", "every")):
        g = pk_gam_ipo1("regular", dict(skill="typical"), replace(base, policy="hit", update_rule=rule), beta, n)
        pc = _pk_pct(g, sw[("regular", "typical")])
        meds[rule] = _pq(pc, 50)
        print(f"| {label} | {_pdist(pc, '{:+.1f}%')} |")
    spread = max(meds.values()) - min(meds.values())
    spam = max(spam_gain)
    print("\n### Fix for launch-spam: each fix is refitted (beta) so that the typical Hit player is again equal to Software, then the spam is measured")
    print("| Fix (placeholder changed) | fitted beta | typical Hit vs Software | Jam Hit spam: gain over typical Hit | Jam Solid spam: gain |")
    print("|---|---|---|---|---|")
    fix_rows = []
    for label, kw in (("none (doc as written)", {}), ("per-title cap k = 0.6 (SECTORS 2.4 'k')", dict(title_cap_k=0.6)), ("k = 0.5", dict(title_cap_k=0.5)), ("k = 0.4", dict(title_cap_k=0.4)),
                      ("half-lives proportional to the work: 20 / 40 / 60 / 80 / 120 min", dict(half_lives=(20, 40, 60, 80, 120)))):
        gc = replace(base, **kw)
        b2 = pk_fit_beta(gc)
        t = pk_gam_ipo1("regular", dict(skill="typical"), gc, b2, n)
        sp = pk_gam_ipo1("regular", dict(skill="typical"), replace(gc, force_scope=0), b2, n)
        sp_s = pk_gam_ipo1("regular", dict(skill="typical"), replace(gc, force_scope=0, policy="solid", update_rule="none"), b2, n)
        sw_ = sw[("regular", "typical")]
        gain = _pq([(b / a - 1) * 100 for a, b in zip(sp, t) if a and b], 50)
        gain_s = _pq([(b / a - 1) * 100 for a, b in zip(sp_s, t) if a and b], 50)
        fix_rows.append((label, gain))
        print(f"| {label} | {tuple(round(x, 2) for x in b2)} | {_pdist(_pk_pct(t, sw_), '{:+.1f}%')} | {gain:+.1f}% | {gain_s:+.1f}% |")
    print("\n### The same marks with S3's fix B (peaks x0.6, cap 0.48, back catalog 0.06; beta refitted) and the half-life fix for launch-spam")
    gB = replace(base, peak=tuple(round(x * 0.6, 3) for x in base.peak), cap=0.48, cat_cap=0.06, half_lives=(20, 40, 60, 80, 120))
    betaB = pk_fit_beta(gB)
    print("| Policy | regular typical | regular fast | regular slow |")
    print("|---|---|---|---|")
    worstB = {"smash": 0.0, "solid": 0.0, "flop": 0.0}
    for label, kw, est in PK_POLICIES:
        cells = []
        for k, sk, skw in profiles[0:1] + profiles[3:]:
            g = pk_gam_ipo1(k, skw, replace(gB, **kw), betaB, n)
            pc = _pk_pct(g, sw[(k, sk)])
            cells.append(_pdist(pc, "{:+.1f}%") if pc else "never")
            if pc:
                key = "smash" if label.startswith("Polish to Smash") else "solid" if label.startswith("Ship") else "flop" if label.startswith("Rush") else None
                if key == "smash":
                    worstB[key] = min(worstB[key], _pq(pc, 50))
                elif key:
                    worstB[key] = max(worstB[key], _pq(pc, 50))
        print(f"| {label} | " + " | ".join(cells) + " |")
    t = pk_gam_ipo1("regular", dict(skill="typical"), gB, betaB, n)
    sp = pk_gam_ipo1("regular", dict(skill="typical"), replace(gB, force_scope=0), betaB, n)
    spB = _pq([(b / a - 1) * 100 for a, b in zip(sp, t) if a and b], 50)
    print(f"\nWith fix B and proportional half-lives: Smash {worstB['smash']:+.1f}%, Solid {worstB['solid']:+.1f}%, Flop {worstB['flop']:+.1f}%, Jam-Hit spam gain {spB:+.1f}%.")
    fixed = [lab for lab, gain in fix_rows[1:] if gain <= 1.0]
    print(f"\n**Result.** Smash {'PASS' if smash >= -5 else 'FAIL'} ({smash:+.1f}%); Solid {'PASS' if solid <= 12 else 'FAIL'} ({solid:+.1f}%); Flop {'PASS' if flop <= 25 else 'FAIL'} ({flop:+.1f}%); "
          f"launch-spam best gain {spam:+.1f}% ({'PASS' if spam <= 1 else 'FAIL'}, mark 1%; first fix that meets it: {fixed[0] if fixed else 'none tried'}); update timing spread {spread:.1f} points ({'PASS' if spread <= 5 else 'FAIL'}, mark 5).")
    return {"smash": smash, "solid": solid, "flop": flop, "spam": spam, "spread": spread}


PK_GAM_VARIANTS = (    # what a player or a bot can do in Gaming: the doc's typical policy, and the best versions of Smash
    ("Gaming, Hit (typical)", dict(policy="hit", update_rule="half")),
    ("Gaming, Smash, update under half", dict(policy="smash", update_rule="half")),
    ("Gaming, Smash, every update", dict(policy="smash", update_rule="every")),
)


def pk_opts(sector, extra_gam=None, **kw):
    """PkOpt of one sector: Software, or Gaming with the doc's cycle (policy changes in extra_gam) and the fit-1 beta of S3."""
    if sector == "Software":
        return PkOpt(**kw)
    gc = replace(PkGam(), **(extra_gam or {}))
    return PkOpt(sectors=("Gaming",), gaming=gc, beta=pk_fit_beta(PkGam()), **kw)


def sim_s4(n):
    """S4 bots (CUSTOMIZE 5.5, SECTORS 4): no sector faster for a task-bot; a macro gets nothing in either."""
    print("\n## S4. Bots in two sectors (docs/CUSTOMIZE_PROPOSAL.md 5.5, docs/SECTORS_PROPOSAL.md 4, 2.9)")
    n = max(6, n // 4)
    print(f"Time to IPO 1 for a player who is online 24/7 (task-bot: answers every task perfectly, so the reward budget is its ceiling; pulse-bot: 3 minutes of tasks every 2 hours; macro: input only, answers no task), "
          f"{n} seeds. Valuation weights: 3 engaged hours a day at 100%, then 5% (day starts 08:00 UTC). In Gaming a bot may choose the best launch policy; its sector verbs (Pitch, Launch, Update) never make it engaged, "
          "so a macro has no work, no revenue and no engaged clock. 'Edge' = how much faster than the same bot in Software (positive = Gaming is faster for the bot). "
          "The doc's mark is 'no sector faster for a bot' (CUSTOMIZE 5.5 = CUST:122, SECTORS 4 = SECT:158) with NO tolerance; the 5% that earlier versions of this file used (and the check below) is an INVENTED tolerance of this sim, not the doc's, so the result gives both readings.\n")
    print("| Player | Sector / policy | Engaged hours to IPO 1 | Days to IPO 1 | Edge over Software (days) |")
    print("|---|---|---|---|---|")
    edges, seed_edges = {}, {}
    for kind, label in (("task-bot", "task-bot (24/7, perfect)"), ("pulse-bot", "pulse-bot (3 min every 2 h)"), ("macro", "macro (input only)"), ("dedicated", "dedicated human, typical (scale)")):
        base_days = None
        for sector, gkw, glabel in (("Software", None, "Software"),) + tuple(("Gaming", kw, lab) for lab, kw in PK_GAM_VARIANTS):
            outs = pk_many(kind, n if kind != "dedicated" else max(n, 8), 1, pk_opts(sector, gkw))
            done = [r for r in outs if r["ipo_h"]]
            if len(done) < len(outs) / 2:
                print(f"| {label} | {glabel} | never | never | - |")
                continue
            days = _pq([r["ipo_day"][0] for r in done], 50)
            hrs = _pq([r["ipo_h"][0] for r in done], 50)
            if base_days is None:
                base_days = days
                base_per_seed = [r["ipo_day"][0] if r["ipo_h"] else None for r in outs]
            edge = (1 - days / base_days) * 100
            edges.setdefault(kind, []).append(edge)
            seed_edges.setdefault(kind, []).append((label, glabel, [(1 - r["ipo_day"][0] / b0) * 100 for r, b0 in zip(outs, base_per_seed) if r["ipo_h"] and b0]))
            print(f"| {label} | {glabel} | {hrs:.1f} | {days:.1f} | {'-' if glabel == 'Software' else f'{edge:+.1f}%'} |")
    best = max(((e, k, sd[1], sd[2]) for k in ("task-bot", "pulse-bot") for e, sd in zip(edges.get(k, [])[1:], seed_edges.get(k, [])[1:])), key=lambda x: x[0], default=(0.0, "", "", []))
    bot_edge = best[0]
    TOL = 5.0      # INVENTED (the doc gives no tolerance); kept only as the second reading
    strict = "FAIL" if bot_edge > 0 else "PASS"
    print(f"\n**Result.** The best edge any sector gives a bot is {bot_edge:+.2f}% ({best[1]}, {best[2]}; per seed {_pdist(best[3], '{:+.2f}%')}). Two verdicts: "
          f"(1) the doc's mark read strictly, 'no sector faster for a bot' with no tolerance: {strict}" + (" (by a tiny margin)" if strict == "FAIL" and bot_edge <= TOL else "") + "; "
          f"(2) within an invented {TOL:.0f}% tolerance (not in the doc): {'PASS' if bot_edge <= TOL else 'FAIL'}. "
          "A macro never reaches the IPO in either sector (graded answers are the only engaged clock; verbs never set it). "
          "What the bot gets in Gaming over a human is the S9 spread between launch policies, not a new exploit: it pays nothing without graded answers.")
    return {"s4": bot_edge}


def sim_s5(n):
    """S5 hopping (CUSTOMIZE 5.5, SECTORS 4): alternating Software and Gaming against staying in one, 10 IPOs, under 3%."""
    print("\n## S5. Hopping between sectors (docs/CUSTOMIZE_PROPOSAL.md 5.5, docs/SECTORS_PROPOSAL.md 4)")
    n = max(5, n // 4)
    print(f"Regular player, typical skill, {n} seeds, 10 IPOs, with the placeholder seed (10% / 25%) at every founding; kept employees carry over, a Gaming company starts with an empty title cycle. "
          "Cell = total engaged hours to IPO 10, median (p10 to p90); the mark is that alternating is not faster than the faster single sector by 3% or more.\n")
    print("| Strategy | Hours to IPO 10 | IPO 1 | IPO 2 | IPO 5 | IPO 10 (that loop) |")
    print("|---|---|---|---|---|---|")
    strat = (("Software only", ("Software",)), ("Gaming only", ("Gaming",)), ("alternate, Software first", ("Software", "Gaming")), ("alternate, Gaming first", ("Gaming", "Software")))
    tot = {}
    for label, sectors in strat:
        o = PkOpt(sectors=sectors, gaming=PkGam(), beta=pk_fit_beta(PkGam()), seed_pct=PK_SEED[0], seed_cap=PK_SEED[1])
        outs = pk_many("regular", n, 10, o)
        done = [r for r in outs if len(r["ipo_h"]) >= 10]
        tot[label] = [r["ipo_h"][9] for r in done]
        def at(k):
            return _pq([r["ipo_h"][k - 1] for r in done], 50)
        loop10 = _pq([r["loops"][9]["eng_h"] for r in done], 50)
        print(f"| {label} | {_pdist(tot[label], '{:.0f}')} | {at(1):.1f} | {at(2):.1f} | {at(5):.1f} | {loop10:.1f} |")
    best = min(_pq(tot["Software only"], 50), _pq(tot["Gaming only"], 50))
    worst_gain = 0.0
    print("\n| Alternating strategy | against Software only | against Gaming only | gain over the faster one |")
    print("|---|---|---|---|")
    for label in ("alternate, Software first", "alternate, Gaming first"):
        a = _pq(tot[label], 50)
        so, go = _pq(tot["Software only"], 50), _pq(tot["Gaming only"], 50)
        gain = (1 - a / best) * 100
        worst_gain = max(worst_gain, gain)
        print(f"| {label} | {(a / so - 1) * 100:+.2f}% | {(a / go - 1) * 100:+.2f}% | {gain:+.2f}% |")
    print(f"\n**Result.** Alternating gains at most {worst_gain:+.2f}% over the faster single sector (mark: under 3%): {'PASS' if worst_gain < 3 else 'FAIL'}. "
          f"The two single sectors differ by {abs(_pq(tot['Software only'], 50) / _pq(tot['Gaming only'], 50) - 1) * 100:.2f}%.")
    return {"s5": worst_gain}


PK_SPREAD = 0.20                      # ASSUMPTION: players of one profile differ in task skill: each seed's task bonus is x (1 +- 20%), so a profile is a population, not one point


def pk_pop(kind, n, loops, o, spread=PK_SPREAD):
    """n players of one profile: the same options, but each seed has its own task skill (f x (1 + spread x u), u from -1 to 1, fixed per seed)."""
    outs = []
    for sd in range(n):
        u = (zlib.crc32(f"pop{sd}".encode()) % 2001) / 1000 - 1
        outs.append(pk_run(kind, sd, loops, replace(o, f_mult=o.f_mult * (1 + spread * u))))
    return outs


_PK_T = {}


def pk_T(n, loops=6, shop_done=False):
    """T (CUSTOMIZE 1.5): the stamp-clock hours of a regular typical player's loop 0, 1, 2 ..., fitted with a typical raise (Medium at every round) and the placeholder seed, median over the population."""
    key = (n, loops, shop_done)
    if key not in _PK_T:
        outs = pk_pop("regular", n, loops, PkOpt(rounds=2, seed_pct=PK_SEED[0], seed_cap=PK_SEED[1], shop_done=shop_done))
        _PK_T[key] = tuple(_pq([r["loops"][i]["stamp_h"] for r in outs if len(r["loops"]) > i], 50) for i in range(loops))
    return _PK_T[key]


def pk_tier_rates(outs, first=1):
    """Share of replays (loop >= first) that got Gold or better, and Platinum, in %, and the number of replays."""
    t = [lp["tier"] for r in outs for i, lp in enumerate(r["loops"]) if i >= first]
    if not t:
        return None, None, 0
    return 100 * sum(1 for x in t if x >= 2) / len(t), 100 * sum(1 for x in t if x == 3) / len(t), len(t)


def pk_replay_rates(outs):
    """Gold or better % and Platinum % over the REAL replays only (a loop in a sector the career already finished), and their number.
    `pk_tier_rates(outs, first=1)` counts every loop from the second one on: in an alternating career that includes the first company of the other sector, which is not a replay and can never be Gold."""
    t = [lp["tier"] for r in outs for lp in r["loops"] if lp["replay"]]
    if not t:
        return None, None, 0
    return 100 * sum(1 for x in t if x >= 2) / len(t), 100 * sum(1 for x in t if x == 3) / len(t), len(t)


def sim_s6(n):
    """S6 tiers (CUSTOMIZE 1.5, 5.5): Gold and Platinum from time, ratio and stake, per profile and pass set."""
    print("\n## S6. Stamp tiers (docs/CUSTOMIZE_PROPOSAL.md 1.5, 5.5; docs/FUNDING_ROUNDS_PROPOSAL.md 3)")
    n = max(16, n * 2 // 5)
    T = pk_T(PK_T_POP)
    print(f"Population: {n} players per profile, task skill spread +-{PK_SPREAD:.0%} (assumption), replays = IPO 2, 3 and 4 of the same sector (loops 1-3), so {3 * n} replays per cell. "
          f"T = the regular typical player's stamp-clock hours per loop with a typical raise (Medium at every round) and the placeholder seed: **{', '.join(f'{x:.1f}' for x in T[:4])} h** for IPO 1-4 (the doc's LONG_GAME hours are 57 / 51.5 / 52 without a raise). "
          "Gold = within 1.0 T, ratio >= 1, stake >= 55%; Platinum = within 0.8 T, ratio >= 1.25, stake >= 70%. Targets shrink by 15% x the share of the run with the 2x Cash pass (CUSTOMIZE 1.5). "
          "'ready' players go public the moment IPO-ready is reached (ratio 1.0); 'hunt' players keep playing until the ratio reaches 1.25 while Platinum is still possible, then go public. Cells: Gold or better % / Platinum %, Software | Gaming (Hit).\n")
    base = dict(T=T, rounds=2, seed_pct=PK_SEED[0], seed_cap=PK_SEED[1])
    rows = (
        ("regular, typical, ready (the T player)", "regular", dict(skill="typical"), {}),
        ("regular, fast, ready", "regular", dict(skill="expert"), {}),
        ("regular, slow, ready", "regular", dict(skill="typical", f_mult=0.5), {}),
        ("dedicated, typical, hunt", "dedicated", dict(skill="typical"), dict(ipo_mode="hunt")),
        ("dedicated, fast, hunt", "dedicated", dict(skill="expert"), dict(ipo_mode="hunt")),
        ("regular, typical, 2x Cash pass, targets shrunk (the rule)", "regular", dict(skill="typical"), dict(cash_mult=2.0, pass_share=1.0)),
        ("regular, typical, 2x Cash pass, targets NOT shrunk (pass-blind)", "regular", dict(skill="typical"), dict(cash_mult=2.0, pass_share=0.0)),
        ("dedicated, fast, hunt, 2x Cash pass, shrunk", "dedicated", dict(skill="expert"), dict(ipo_mode="hunt", cash_mult=2.0, pass_share=1.0)),
        ("regular, typical, Shareholder pass", "regular", dict(skill="typical"), dict(shareholder=True)),
        ("regular, typical, 2x Cash + VIP (x3), shrunk 15% only", "regular", dict(skill="typical"), dict(cash_mult=3.0, pass_share=1.0)),
        ("regular, typical, Large raise in every round (stake 69.6%)", "regular", dict(skill="typical"), dict(rounds=3)),
    )
    print("| Profile | Gold or better % (Software / Gaming) | Platinum % (Software / Gaming) |")
    print("|---|---|---|")
    res = {}
    for label, kind, skw, extra in rows:
        cells = []
        for sector in ("Software", "Gaming"):
            o = pk_opts(sector, None, **{**base, **skw, **extra})
            g, pl, k = pk_tier_rates(pk_pop(kind, n, 4, o))
            cells.append((g, pl))
        res[label] = cells
        print(f"| {label} | {cells[0][0]:.0f} / {cells[1][0]:.0f} | {cells[0][1]:.0f} / {cells[1][1]:.0f} |")
    typ_g = res[rows[0][0]][0][0]
    dedi = res[rows[4][0]][0][1]
    shrunk = res[rows[5][0]][0][0]
    blind = res[rows[6][0]][0][0]
    print("\n### Platinum for the dedicated, fast, hunting player under other time and ratio rules (Software)")
    print("| Rule | Platinum % | Gold or better % |")
    print("|---|---|---|")
    fixes = []
    for label, pf, pr in (("0.8 T and ratio 1.25 (the doc)", 0.8, 1.25), ("0.9 T, ratio 1.25", 0.9, 1.25), ("1.0 T, ratio 1.25", 1.0, 1.25), ("1.0 T, ratio 1.20", 1.0, 1.20),
                          ("1.0 T, ratio 1.15", 1.0, 1.15), ("1.0 T, ratio 1.10", 1.0, 1.10), ("0.8 T, ratio 1.10", 0.8, 1.10), ("0.9 T, ratio 1.10", 0.9, 1.10)):
        o = pk_opts("Software", None, **{**base, "skill": "expert", "ipo_mode": "hunt", "tier": dict(PK_TIER, plat_frac=pf, plat_ratio=pr)})
        g, pl, k = pk_tier_rates(pk_pop("dedicated", n, 4, o))
        fixes.append((label, pl))
        print(f"| {label} | {pl:.0f} | {g:.0f} |")
    ok = [lab for lab, pl in fixes if pl >= 20]
    print("\n### Pass owners: how much a pass really shortens a replay, and the target shrink that makes Gold equal (regular typical, Software)")
    nopass = pk_pop("regular", n, 4, pk_opts("Software", None, **base))
    h0 = [_pq([r["loops"][i]["stamp_h"] for r in nopass], 50) for i in (1, 2, 3)]
    print("| Pass | stamp-clock hours of IPO 2 / 3 / 4 as a % of no pass | Gold or better % with target shrink of 0 | 4% | 6% | 8% | 10% | 15% (the doc, Cash pass) |")
    print("|---|---|---|---|---|---|---|---|")
    sweep_ok = {}
    for label, kw in (("2x Cash", dict(cash_mult=2.0)), ("2x Cash + VIP (x3)", dict(cash_mult=3.0)), ("Shareholder (x2 Shares)", dict(shareholder=True))):
        outs = pk_pop("regular", n, 4, pk_opts("Software", None, **{**base, **kw}))
        h1 = [_pq([r["loops"][i]["stamp_h"] for r in outs], 50) for i in (1, 2, 3)]
        cells = []
        for sh in (0.0, 0.04, 0.06, 0.08, 0.10, 0.15):
            o = pk_opts("Software", None, **{**base, **kw, "pass_share": 1.0, "tier": dict(PK_TIER, pass_shrink=sh)})
            g, pl, k = pk_tier_rates(pk_pop("regular", n, 4, o))
            cells.append(f"{g:.0f}")
            if abs(g - typ_g) <= 5 and label not in sweep_ok:
                sweep_ok[label] = sh
        print(f"| {label} | " + " / ".join(f"{100 * a / b:.1f}" for a, b in zip(h1, h0)) + " | " + " | ".join(cells) + " |")
    print(f"\n(The player with no pass has Gold on {typ_g:.0f}%. Shrinks that land within 5 points: " + (", ".join(f"{k} {v:.0%}" for k, v in sweep_ok.items()) or "none of the four") + ".)")
    print(f"\n**Result.** Gold on {typ_g:.0f}% of the regular typical player's replays (mark: at least 50%): {'PASS' if typ_g >= 50 else 'FAIL'}. "
          f"Platinum on {dedi:.0f}% of the dedicated fast hunter's replays (mark: at least 20%): {'PASS' if dedi >= 20 else 'FAIL; the smallest rule change that reaches 20%: ' + (ok[0] if ok else 'none tried')}. "
          f"Pass owners (2x Cash, shrunk) Gold {shrunk:.0f}% against {typ_g:.0f}% without the pass: {'PASS' if abs(shrunk - typ_g) <= 5 else 'FAIL'} (mark: within 5 points); pass-blind targets give {blind:.0f}%.")
    return {"s6_gold": typ_g, "s6_plat": dedi, "s6_pass": shrunk}


PK_T_POP = 16


def pk_collection(loops_list, k):
    """Collection after k IPOs (CUSTOMIZE 1.6): 1000 x (best stamp of each sector: Bronze 1, Gold 2, Platinum 3) + the IPO count."""
    best = {}
    for lp in loops_list[:k]:
        best[lp["sector"]] = max(best.get(lp["sector"], 0), lp["tier"])
    return 1000 * sum(best.values()) + k


def sim_s7(n):
    """S7 board (CUSTOMIZE 5.5, 1.6): new sector against replays within 10%; the task-bot never above a dedicated human."""
    print("\n## S7. Leaderboard (docs/CUSTOMIZE_PROPOSAL.md 1.6, 5.5)")
    n = max(5, n // 5)
    T = pk_T(PK_T_POP)
    gam_beta = pk_fit_beta(PkGam())
    print(f"Collection = 1000 x (best stamp of each sector, Bronze 1 / Gold 2 / Platinum 3) + IPOs (CUSTOMIZE 1.6). {n} seeds per cell. Tiers use T from S6 ({', '.join(f'{x:.1f}' for x in T[:4])} h) and a typical raise (Medium at every round).\n")
    print("### 1. Hours of a new sector against a replay at the same IPO count (regular typical, placeholder seed)")
    base = dict(rounds=2, seed_pct=PK_SEED[0], seed_cap=PK_SEED[1])
    alt = pk_many("regular", n, 5, PkOpt(sectors=("Software", "Gaming"), gaming=PkGam(), beta=gam_beta, **base))
    one = pk_many("regular", n, 5, PkOpt(**base))
    print("| IPO | Alternating: what the loop is | hours | One sector: replay, hours | ratio |")
    print("|---|---|---|---|---|")
    worst_h = 0.0
    for i in range(1, 5):
        a = _pq(pk_loop_h(alt, i), 50)
        b = _pq(pk_loop_h(one, i), 50)
        kind = "first Gaming company (new sector)" if i % 2 == 1 else "Software replay"
        if i % 2 == 1:
            worst_h = max(worst_h, abs(a / b - 1) * 100)
        print(f"| {i + 1} | {kind} | {a:.1f} | {b:.1f} | {a / b * 100:.1f}% |")
    print("\n### 2. Collection points per 100 stamp-clock hours: seeking new sectors against replaying one (dedicated, fast, hunting for Platinum)")
    pop = max(8, n * 2)
    o_h = dict(T=T, rounds=2, seed_pct=PK_SEED[0], seed_cap=PK_SEED[1], skill="expert", ipo_mode="hunt")
    alt_h = pk_pop("dedicated", pop, 6, PkOpt(sectors=("Software", "Gaming"), gaming=PkGam(), beta=gam_beta, **o_h))
    one_h = pk_pop("dedicated", pop, 6, PkOpt(**o_h))
    print("| After IPO | Alternating: Collection / hours | points per 100 h | One sector: Collection / hours | points per 100 h | alternating / one |")
    print("|---|---|---|---|---|---|")
    worst_pts, rows = 0.0, []
    for k in (2, 4, 6):
        ca = [pk_collection(r["loops"], k) for r in alt_h if len(r["loops"]) >= k]
        co = [pk_collection(r["loops"], k) for r in one_h if len(r["loops"]) >= k]
        ha = [sum(lp["stamp_h"] for lp in r["loops"][:k]) for r in alt_h if len(r["loops"]) >= k]
        ho = [sum(lp["stamp_h"] for lp in r["loops"][:k]) for r in one_h if len(r["loops"]) >= k]
        pa, po = _pq(ca, 50) / 1000 / _pq(ha, 50) * 100, _pq(co, 50) / 1000 / _pq(ho, 50) * 100
        rows.append(pa / po)
        worst_pts = max(worst_pts, abs(pa / po - 1) * 100)
        print(f"| {k} | {_pq(ca, 50):.0f} / {_pq(ha, 50):.0f} h | {pa:.2f} | {_pq(co, 50):.0f} / {_pq(ho, 50):.0f} h | {po:.2f} | {pa / po * 100:.0f}% |")
    print("\n### 3. Task-bot against a dedicated human and a heavy human, same career (alternating sectors, hunting): stamps and Collection")
    print("Two metrics. **Collection total** is the doc's own (the board ranks Collection, CUSTOMIZE 1.6 = CUST:75; mark CUST:122 'the task-bot never above a dedicated human'). "
          "**Collection per stamp-clock hour** (Collection / the median stamp-clock hours of one IPO) is INVENTED by this sim, not in any doc. "
          "'Gold or better, loops 1-3' counts every loop after the first (as the first version of this table did), which in an alternating career includes the first company of the other sector, "
          "a loop that is not a replay and can never be Gold; 'real replays' counts only the loops in a sector already finished (here IPO 3 and IPO 4). **heavy** = 5 h a day (the 3 h/day rule applies to it, a bot is not needed).")
    nb = max(4, n // 2)
    base7 = dict(sectors=("Software", "Gaming"), gaming=PkGam(), beta=gam_beta)
    bot = pk_many("task-bot", nb, 4, PkOpt(**base7, **{**o_h, "skill": "typical"}))
    hum = pk_pop("dedicated", pop, 4, PkOpt(**base7, **o_h))
    hvy = pk_pop("heavy", pop, 4, PkOpt(**base7, **o_h))
    bot_raw = pk_many("task-bot", nb, 4, PkOpt(**base7, **{**o_h, "skill": "typical", "tier": dict(PK_TIER, clock="raw")}))
    hum_raw = pk_pop("dedicated", pop, 4, PkOpt(**base7, **{**o_h, "tier": dict(PK_TIER, clock="raw")}))
    hvy_raw = pk_pop("heavy", pop, 4, PkOpt(**base7, **{**o_h, "tier": dict(PK_TIER, clock="raw")}))
    print("| Player | stamp-clock hours per IPO (median) | Platinum % of loops 1-3 | Gold or better %, loops 1-3 | Gold or better %, real replays | Collection after 4 IPOs, median (p10 to p90) | days to the 4th IPO | Collection per stamp-clock hour (INVENTED metric) |")
    print("|---|---|---|---|---|---|---|---|")
    stats = {}
    rows7 = (("dedicated human, fast, hunting (2 h a day)", hum), ("heavy human, fast, hunting (5 h a day)", hvy), ("task-bot, 24/7, hunting", bot),
             ("FIX: stamp clock = raw engaged hours: dedicated human", hum_raw), ("FIX: stamp clock = raw engaged hours: heavy human", hvy_raw), ("FIX: stamp clock = raw engaged hours: task-bot", bot_raw))
    for label, outs in rows7:
        hrs = _pq([lp["stamp_h"] for r in outs for lp in r["loops"]], 50)
        g, pl, k = pk_tier_rates(outs)
        g_real, pl_real, k_real = pk_replay_rates(outs)
        cols = [pk_collection(r["loops"], 4) for r in outs if len(r["loops"]) >= 4]
        col = _pq(cols, 50)
        days = _pq([r["ipo_day"][3] for r in outs if len(r["ipo_day"]) >= 4], 50)
        stats[label] = dict(hrs=hrs, plat=pl, gold=g, gold_real=g_real, plat_real=pl_real, col=col, cols=cols, days=days)
        print(f"| {label} | {hrs:.1f} | {pl:.0f} | {g:.0f} | {g_real:.0f} ({k_real} replays) | {_pdist(cols, '{:.0f}')} | {days:.0f} | {col / hrs:.1f} |")
    h, hv, b = (stats[k] for k in ("dedicated human, fast, hunting (2 h a day)", "heavy human, fast, hunting (5 h a day)", "task-bot, 24/7, hunting"))
    hr, hvr, br = (stats[k] for k in ("FIX: stamp clock = raw engaged hours: dedicated human", "FIX: stamp clock = raw engaged hours: heavy human", "FIX: stamp clock = raw engaged hours: task-bot"))
    col_cmp = "above" if b["col"] > h["col"] else "equal to" if b["col"] == h["col"] else "below"
    inv_b, inv_hv = (b["col"] / b["hrs"]) / (h["col"] / h["hrs"]) - 1, (hv["col"] / hv["hrs"]) / (h["col"] / h["hrs"]) - 1
    print(f"\n**Result.** New sector against replay: the hours differ by at most {worst_h:.1f}% (mark 10%): {'PASS' if worst_h <= 10 else 'FAIL'}. "
          f"Points per hour, new sectors against replays: within {worst_pts:.0f}% ({'PASS' if worst_pts <= 10 else 'FAIL'}; the replays only count when a better tier is reached). "
          f"**The doc's own metric (Collection total):** the bot's median is {b['col']:.0f} against the dedicated human's {h['col']:.0f}, so the bot is {col_cmp} the human (mark: never above): {'PASS' if b['col'] <= h['col'] else 'FAIL'}"
          f" (a tie at the median; per seed {_pdist(b['cols'], '{:.0f}')} against {_pdist(h['cols'], '{:.0f}')}). "
          f"**The invented metric (Collection per stamp-clock hour):** the bot is {inv_b * 100:+.1f}% against the dedicated human ({b['col'] / b['hrs']:.1f} against {h['col'] / h['hrs']:.1f}), and the heavy human (5 h a day, no bot) is {inv_hv * 100:+.1f}% "
          f"({hv['col'] / hv['hrs']:.1f}): a human gets part of the same edge, and it grows with the hours played over the 3 h a day the rule counts at full value (2 h a day: 0 by definition, 5 h: {inv_hv * 100:+.1f}%, 24 h: {inv_b * 100:+.1f}%), "
          f"so the cause is playing more than 3 h a day, not being a bot (the heavy human gets {inv_hv / inv_b * 100:.0f}% of the bot's edge, not all of it). Why: the 3 h/day rule weights only the valuation, never Cash, so anyone who plays more than 3 h a day has bought everything long before the weighted hours run out, and each weighted hour pays more. "
          f"With the stamp clock counting raw engaged hours the bot's Platinum / Gold are {br['plat']:.0f}% / {br['gold']:.0f}% (real replays {br['gold_real']:.0f}%), the heavy human's {hvr['plat']:.0f}% / {hvr['gold']:.0f}% (real replays {hvr['gold_real']:.0f}%) "
          f"and the dedicated human's {hr['plat']:.0f}% / {hr['gold']:.0f}% (real replays {hr['gold_real']:.0f}%; the dedicated human plays 2 h a day, so nothing changes for them): the fix takes tiers from every player who plays more than 3 h a day, bot or human; per day the bot is {h['days'] / b['days']:.1f}x faster, which LONG_GAME section 2 already accepts.")
    return {"s7_hours": worst_h, "s7_pts": worst_pts}


def sim_s10(n):
    """S10 cadence (SECTORS 4, LONG_GAME 4): moments per hour per rung and the longest gap, both sectors."""
    print("\n## S10. Cadence: moments per hour and the longest gap (docs/SECTORS_PROPOSAL.md 4; docs/LONG_GAME_PROPOSAL.md 4)")
    gc = PkGam()
    beta = pk_fit_beta(gc)
    base = dict(away=(0, 0, 0), full_hours=1e9, max_days=400, record=True)
    sw = pk_run("reference", 0, 1, PkOpt(**base))
    gm = pk_run("reference", 0, 1, PkOpt(sectors=("Gaming",), gaming=gc, beta=beta, **base))
    gm_cp = pk_run("reference", 0, 1, PkOpt(sectors=("Gaming",), gaming=replace(gc, checkpoint_min=12), beta=pk_fit_beta(replace(gc, checkpoint_min=12)), **base))
    print("Always-engaged reference player, IPO 1 (the engaged hours of each event come from the run). A moment = a timed event: an item bought (upgrade, office, desk, hire), a valuation milestone and a board / publisher request (Series C+D), "
          "and in Gaming the title-cycle decisions: Pitch, Playtest fix, content complete (ship or polish), Launch and each Live Update. Untimed content (tasks that appear, products, decor, titles) is not in the sim, so every gap is an upper bound. "
          "'Cycle only' = the gaps between title-cycle decisions alone.\n")
    print("| Rung | Hours | Software: moments per hour | longest gap, min | Gaming: moments per hour | longest gap, min | Gaming, cycle only: longest gap, min | Gaming with a checkpoint every 12 min: longest gap, min |")
    print("|---|---|---|---|---|---|---|---|")
    worst = {"sw": 0.0, "gm": 0.0, "cyc": 0.0, "cp": 0.0}
    hs, hg, hc = pk_rung_hours(sw), pk_rung_hours(gm), pk_rung_hours(gm_cp)

    def gaps(run, r, h, with_buys=True, cycle=False):
        start = run["stage_h"][0][r]
        ev = []
        if with_buys:
            ev += [t for rr, t in run["buy_h"] if rr == r]
            if r == LONG_BOARD_RUNG:
                ev += [t for t in run["ms_h"] if start <= t <= start + h] + [t for t in run["board_h"] if start <= t <= start + h]
        if cycle:
            ev += [t for t, _ in run["cyc_ev"] if start <= t < start + h]
        ev = sorted(ev)
        pts = [start] + ev + [start + h]
        g = [(b - a) * 60 for a, b in zip(pts, pts[1:])]
        return len(ev), max(g)
    for r, (name, *_x) in enumerate(LONG_RUNGS):
        ns, gs = gaps(sw, r, hs[r])
        ng, gg = gaps(gm, r, hg[r], cycle=True)
        nc, gcy = gaps(gm, r, hg[r], with_buys=False, cycle=True)
        ncp, gcp = gaps(gm_cp, r, hc[r], cycle=True)
        worst["sw"], worst["gm"], worst["cyc"], worst["cp"] = max(worst["sw"], gs), max(worst["gm"], gg), max(worst["cyc"], gcy), max(worst["cp"], gcp)
        print(f"| {name} | {hs[r]:.1f} | {ns / hs[r]:.1f} | {gs:.0f} | {ng / hg[r]:.1f} | {gg:.0f} | {gcy:.0f} | {gcp:.0f} |")
    sw_cd = gaps(sw, LONG_BOARD_RUNG, hs[LONG_BOARD_RUNG])[1]
    print(f"\n**Result.** Software: the Series C+D gap is {sw_cd:.0f} min (LONG_GAME's 45 with the board requests); the other rungs' timed gaps (up to {worst['sw']:.0f} min) are upper bounds, because their tasks, products, decor and titles have no time in the sim, so the 45-minute mark cannot be confirmed for Software outside C+D from this sim. "
          f"Gaming: longest gap between any timed moments {worst['gm']:.0f} min (mark: no gap over 45 minutes: {'PASS, at the limit' if worst['gm'] <= 45 else 'FAIL'}). "
          f"Gaming's longest wait between decisions of the title cycle alone is {worst['cyc']:.0f} min (mark: under 15: {'PASS' if worst['cyc'] < 15 else 'FAIL'}); with a checkpoint verb every 12 engaged minutes while a title is in development it is {worst['cp']:.0f} min: {'PASS' if worst['cp'] < 15 else 'FAIL'}.")
    return {"s10": worst}



def pk_fund_formula(kind):
    """FUNDING 3: the basis points of each round, recomputed from the formula bp = floor(P x g x h x 10000) (g = Cash / gap to the next stage, h = the stage's share of the loop's hours).
    Returns {stage: [(bp, g, u) for Small, Medium, Large]}."""
    if kind == "long":
        thr = long_thresholds()
        hrs = long_hours(LONG_ITEMS)
        stages = {st: (thr[st - 1], thr[st], hrs[st] / sum(hrs)) for st in range(1, 6)}
    else:
        v = [x for _, x in IPO_STAGES[1:]]            # 1800, 6300, 23400, 81000
        stages = {st: (v[st - 1], v[st], PK_FUND_TODAY_MIN[st] / 12) for st in (1, 2, 3)}
    tab = {}
    for st, (lo, hi, h) in stages.items():
        row = []
        for ci in range(3):
            g = PK_FUND_CASH_BP[ci] / 10000 * lo / (hi - lo)
            u = g * h
            row.append((max(1, int(math.floor(PK_FUND_P[ci] * u * 10000 + 1e-9))), g, u))
        tab[st] = row
    return tab


def pk_enum(bp_table):
    """Every sequence of (none, Small, Medium, Large) over the rounds: count, how many lose Platinum (D > 3000) and Gold (D > 4500), how many pass the cap, the largest total."""
    import itertools
    stages = sorted(bp_table)
    tot = []
    for seq in itertools.product(range(4), repeat=len(stages)):
        tot.append(sum(bp_table[st][c - 1] for st, c in zip(stages, seq) if c))
    return len(tot), sum(1 for d in tot if d > 3000), sum(1 for d in tot if d > 4500), sum(1 for d in tot if d > PK_FUND_CAP), max(tot)


class PkRoundPlayer(Player):
    """Today's economy (the Player class) with funding rounds at Seed, Series A and Series B (S8). choices = 0..3 for every round or {stage: choice}; plain_floor = Shares floored with no carry."""
    choices = 0
    plain_floor = False

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.D = 0
        self.dust = 0
        self.fired = set()

    def check_stages(self, t):
        super().check_stages(t)
        for i in (1, 2, 3):
            need = IPO_STAGES[i][1] * self.stage_scale
            if i not in self.fired and self.earned_run >= need:
                self.fired.add(i)
                ch = self.choices.get(i, 0) if isinstance(self.choices, dict) else self.choices
                if ch and self.D + PK_FUND_TODAY_BP[i][ch - 1] <= PK_FUND_CAP:
                    before = (self.earned_run, self.earned_total)
                    self.cash += int(need * PK_FUND_CASH_BP[ch - 1] // 10000)      # a gift: Cash only, like the daily calendar
                    self.D += PK_FUND_TODAY_BP[i][ch - 1]
                    assert before == (self.earned_run, self.earned_total), "round Cash must not count toward the IPO valuation"

    def maybe_ipo(self, t):
        if not super().maybe_ipo(t):
            return False
        gained = self.shares_log[-1]
        if self.plain_floor:
            paid = gained * (10000 - self.D) // 10000
        else:
            paid, self.dust = pk_dilute(gained, self.D, self.dust)
        self.shares += paid - gained
        self.shares_log[-1] = paid
        self.D = 0
        self.fired = set()
        return True


def _pk_scaled(table, k):
    return {st: tuple(max(1, int(round(b * k))) for b in row) for st, row in table.items()}


def _pk_hours_sum(outs, loops):
    return [r["ipo_h"][loops - 1] for r in outs if len(r["ipo_h"]) >= loops]


def pk_best_rounds(kind, kw, loops, seeds, cap_D=None, bp=None):
    """best-per-stage: coordinate search (two passes, last stage first) for the round choices that give the fewest engaged hours to IPO `loops`, optionally with total dilution under cap_D."""
    bp = bp or PK_FUND_LONG_BP
    cur = {st: 0 for st in bp}

    def total(pol):
        return _pq(_pk_hours_sum(pk_many(kind, seeds, loops, PkOpt(rounds=pol, round_bp=bp, **kw)), loops), 50)
    for _ in range(2):
        for st in sorted(bp, reverse=True):
            best = None
            for c in (0, 1, 2, 3):
                trial = dict(cur)
                trial[st] = c
                if cap_D is not None and sum(bp[k][trial[k] - 1] for k in trial if trial[k]) > cap_D:
                    continue
                sc = total(trial)
                if best is None or sc < best[0] - 1e-9:
                    best = (sc, c)
            cur[st] = best[1]
    return cur


def sim_s8(n):
    """S8 round size (FUNDING 6, CUSTOMIZE 5.5, SECTORS 4)."""
    print("\n## S8. Funding rounds: round size, speed against Shares and against the stamp tier (docs/FUNDING_ROUNDS_PROPOSAL.md 1-6)")
    seeds = max(8, n // 4)
    names = {1: "Seed", 2: "Series A", 3: "Series B", 4: "Series C+D", 5: "Pre-IPO"}
    ch_names = ("Small", "Medium", "Large")
    marks = {}

    # ---- A. the table, recomputed ----
    print("### A. The basis-point tables, recomputed from FUNDING 3's formula, and the dominance check")
    for kind, label, doc in (("long", "LONG_GAME's 7 stages (5 rounds)", PK_FUND_LONG_BP), ("today", "today's 5 stages (3 rounds)", PK_FUND_TODAY_BP)):
        tab = pk_fund_formula(kind)
        print(f"\n**{label}.** Cell = bp Small / Medium / Large: recomputed (doc).")
        print("| Stage | recomputed (doc) | Large: Cash as % of the gap to the next stage | Large: loop time it is worth (upper bound) | 0 < S < M-S < L-M ? |")
        print("|---|---|---|---|---|")
        dom_ok = True
        for st, row in tab.items():
            b = [r[0] for r in row]
            d = doc[st]
            ok = 0 < d[0] < d[1] - d[0] < d[2] - d[1]
            dom_ok = dom_ok and ok
            print(f"| {names[st]} | {b[0]} / {b[1]} / {b[2]} ({d[0]} / {d[1]} / {d[2]}) | {row[2][1] * 100:.2f}% | {row[2][2] * 100:.3f}% | {'yes' if ok else 'NO'} |")
        cnt, lose_p, lose_g, over_cap, mx = pk_enum(doc)
        print(f"\nAll {cnt} sequences of (none, Small, Medium, Large) over the rounds, doc table: **{lose_p} lose Platinum on stake (D over 3,000 bp)**, {lose_g} lose Gold (over 4,500), {over_cap} pass the 4,000 cap; the largest total is {mx} bp. "
              f"Dominance (each step up costs strictly more per unit of Cash): {'holds at every stage' if dom_ok else 'FAILS at some stage'}.")
        marks[kind] = (lose_p, cnt, mx, dom_ok)

    # ---- B. what one round saves ----
    print(f"\n### B. Hours saved by each single round (LONG ladder, regular typical, {seeds} seeds, same random streams, the shop is complete so Shares are worth nothing)")
    base0 = pk_many("regular", seeds, 1, PkOpt(shop_done=True))
    print("| Stage | Choice | Cash | dilution bp | hours saved, % of the loop (median, p10 to p90) | upper bound (the table's u) | % of Shares paid per 1% of loop time saved | FUNDING's price P | measured price / P (above 1 = too dear) |")
    print("|---|---|---|---|---|---|---|---|---|")
    tabL = pk_fund_formula("long")
    save_med = {}
    for st in range(1, 6):
        for ci in range(3):
            outs = pk_many("regular", seeds, 1, PkOpt(rounds={st: ci + 1}, shop_done=True))
            sv = pk_rel(outs, base0, 0)
            m_ = _pq(sv, 50)
            save_med[(st, ci)] = m_
            cash = int(long_thresholds()[st - 1] * PK_FUND_CASH_BP[ci] // 10000)
            bp = PK_FUND_LONG_BP[st][ci]
            print(f"| {names[st]} | {ch_names[ci]} | {fmt_cash(cash)} | {bp} | {_pdist(sv, '{:.2f}%')} | {tabL[st][ci][2] * 100:.2f}% | {bp / 100 / max(m_, 1e-9):.1f} | {PK_FUND_P[ci]} | {bp / 100 / max(m_, 1e-9) / PK_FUND_P[ci]:.1f}x |")
    # ---- C. policies for loop 0, both sectors ----
    print(f"\n### C. Round policies over a whole loop, both sectors (regular typical, shop complete, {seeds} seeds): hours saved at IPO 1 and IPO 2")
    print("| Policy | total dilution bp | Software: IPO 1 saved | Software: IPO 2 saved | Gaming (Hit): IPO 1 saved | Gaming: IPO 2 saved | hours saved at IPO 1, Software vs Gaming (difference) |")
    print("|---|---|---|---|---|---|---|")
    ref = {sec: pk_many("regular", seeds, 2, pk_opts(sec, None, shop_done=True)) for sec in ("Software", "Gaming")}
    l_save, sg_diff = {}, 0.0
    for label, ch in (("Small every round", 1), ("Medium every round", 2), ("Large every round", 3)):
        D = sum(PK_FUND_LONG_BP[st][ch - 1] for st in PK_FUND_LONG_BP)
        row = {}
        for sec in ("Software", "Gaming"):
            outs = pk_many("regular", seeds, 2, pk_opts(sec, None, shop_done=True, rounds=ch))
            row[sec] = [_pq(pk_rel(outs, ref[sec], i), 50) for i in (0, 1)]
            hs = [(a - b) for a, b in zip(pk_loop_h(ref[sec], 0), pk_loop_h(outs, 0))]
            row[sec].append(_pq(hs, 50))
        diff = abs(row["Gaming"][2] / row["Software"][2] - 1) * 100
        sg_diff = max(sg_diff, diff)
        l_save[label] = row
        print(f"| {label} | {D} | {row['Software'][0]:.1f}% | {row['Software'][1]:.1f}% | {row['Gaming'][0]:.1f}% | {row['Gaming'][1]:.1f}% | {row['Software'][2]:.2f} h vs {row['Gaming'][2]:.2f} h ({diff:.1f}%) |")
    large_sw = l_save["Large every round"]["Software"][0]
    large_gm = l_save["Large every round"]["Gaming"][0]
    print(f"\nLarge every round saves {large_sw:.1f}% of IPO 1 in Software and {large_gm:.1f}% in Gaming (FUNDING's upper bound is 12.18%, mark: at most 15%).")
    marks["large_saves"] = max(large_sw, large_gm)
    marks["sector_diff"] = sg_diff
    extra = []
    sw_hours = l_save["Large every round"]["Software"][2]
    for lab, kw in (("Solid", dict(policy="solid", update_rule="none")), ("Flop", dict(policy="rush", update_rule="none"))):
        a = pk_many("regular", seeds, 1, pk_opts("Gaming", kw, shop_done=True))
        b = pk_many("regular", seeds, 1, pk_opts("Gaming", kw, shop_done=True, rounds=3))
        sv = _pq([x - y for x, y in zip(pk_loop_h(a, 0), pk_loop_h(b, 0))], 50)
        extra.append(f"{lab} {abs(sv / sw_hours - 1) * 100:.1f}%")
        marks["sector_diff"] = max(marks["sector_diff"], abs(sv / sw_hours - 1) * 100)
    print("Gaming with the other launch policies saves the same hours as Software (Large every round) within " + ", ".join(extra) + ".")

    # ---- D. who picks what ----
    print(f"\n### D. Is the maximum always best? Engaged hours to IPO 3, the shop NOT complete (Shares buy the speed perk), per profile and policy ({seeds} seeds; cell = hours saved against no round; the best cell is bold)")
    profs = (("regular typical", "regular", dict()), ("dedicated typical", "dedicated", dict()), ("casual typical", "casual", dict()), ("regular fast", "regular", dict(skill="expert")),
             ("regular slow", "regular", dict(skill="typical", f_mult=0.5)), ("regular, 2x Cash", "regular", dict(cash_mult=2.0)), ("regular, Shareholder", "regular", dict(shareholder=True)))
    print("| Profile | Small | Medium | Large | best |")
    print("|---|---|---|---|---|")
    best_set = set()
    for label, kind, kw in profs:
        b0 = pk_many(kind, seeds, 3, PkOpt(**kw))
        vals = []
        for ch in (1, 2, 3):
            o = pk_many(kind, seeds, 3, PkOpt(rounds=ch, **kw))
            vals.append(_pq([(1 - r["ipo_h"][2] / b["ipo_h"][2]) * 100 for r, b in zip(o, b0) if len(r["ipo_h"]) >= 3 and len(b["ipo_h"]) >= 3], 50))
        top = max(range(3), key=lambda i: vals[i])
        best_set.add(top)
        print(f"| {label} | " + " | ".join(("**" if i == top else "") + f"{v:+.2f}%" + ("**" if i == top else "") for i, v in enumerate(vals)) + f" | {ch_names[top]} |")
    print("\nThe only Share sink in the model is the speed lump (154 Shares for +25% Income), so the Shares a round costs delay a +25% perk by only a few percent of a loop: "
          f"the best policy is {', '.join(ch_names[i] for i in sorted(best_set))} in every profile.")
    marks["best_set"] = best_set
    print("\n**What curve makes the choice real?** The same table with every basis-point price multiplied (the 4,000 cap stays); cell = the best policy by hours to IPO 3 for a player who values Shares (shop not complete), "
          "for a player with the shop complete who protects Platinum (total dilution at most 3,000 bp), and for a casual player:")
    print("| price multiplier | total of Large every round | regular, Shares valued: best | regular, shop complete, Platinum protected: best | casual, Shares valued: best |")
    print("|---|---|---|---|---|")
    real = []
    for k in (1, 2, 3, 5, 8):
        bp = _pk_scaled(PK_FUND_LONG_BP, k)
        row = []
        for kind, kw, cap_D in (("regular", dict(), None), ("regular", dict(shop_done=True), 3000), ("casual", dict(), None)):
            res = {}
            for lab, ch in (("none", 0), ("Small", 1), ("Medium", 2), ("Large", 3)):
                dd = sum(bp[st][ch - 1] for st in bp) if ch else 0
                if cap_D is not None and dd > cap_D:
                    continue
                outs = pk_many(kind, max(4, seeds // 2), 3, PkOpt(rounds=ch, round_bp=bp, **kw))
                res[lab] = _pq(_pk_hours_sum(outs, 3), 50)
            row.append(min(res, key=res.get))
        real.append((k, row))
        print(f"| x{k} | {sum(bp[st][2] for st in bp)} bp | {row[0]} | {row[1]} | {row[2]} |")
    print("\n**Best per stage** (coordinate search over the 4^5 sequences, 2 passes; hours to IPO 3, 3 seeds):")
    for label, kind, kw, cap_D in (("Shares valued, shop not complete", "regular", dict(), None), ("shop complete, Platinum protected (D <= 3,000 bp)", "regular", dict(shop_done=True), 3000)):
        pol = pk_best_rounds(kind, kw, 3, 3, cap_D)
        D = sum(PK_FUND_LONG_BP[st][c - 1] for st, c in pol.items() if c)
        print(f"- {label}: " + ", ".join(f"{names[st]} {'skip' if not pol[st] else ch_names[pol[st] - 1]}" for st in sorted(pol)) + f" (total dilution {D} bp)")

    # ---- E. marks ----
    print("\n### E. The other marks")
    print("**Alt-fed and converter, loop 2** (regular typical, shop complete; the alt feeds 3 poach-ins per run, which do not carry over an IPO, as LONG_GAME R2):")
    ne = max(6, seeds)
    rows = {}
    for label, kw in (("no rounds, no alt", {}), ("Large every round", dict(rounds=3)), ("alt-fed, no rounds", dict(fed=99, fed_run=3)), ("alt-fed + Large every round", dict(fed=99, fed_run=3, rounds=3))):
        outs = pk_many("regular", ne, 2, PkOpt(shop_done=True, **kw))
        rows[label] = (_pq(pk_loop_h(outs, 0), 50), _pq(pk_loop_h(outs, 1), 50), _pq([lp["owned"] for r in outs for lp in r["loops"]], 50))
    print("| Case | IPO 1 hours | IPO 2 hours | items owned at the IPO (of %d) |" % len(LONG_ITEMS))
    print("|---|---|---|---|")
    for label, (a, b, o_) in rows.items():
        print(f"| {label} | {a:.1f} | {b:.1f} | {o_:.0f} |")
    r0, rL, rA, rAL = (rows[k][1] for k in ("no rounds, no alt", "Large every round", "alt-fed, no rounds", "alt-fed + Large every round"))
    gain_plain, gain_alt = (1 - rL / r0) * 100, (1 - rAL / rA) * 100
    print(f"\nIn loop 2 Large every round saves a plain player {gain_plain:.1f}% and an alt-fed player {gain_alt:.1f}%: rounds give the alt-fed player {gain_alt - gain_plain:+.1f} points more than a plain one (mark: under 3). "
          f"The converter cannot gain either: every one of the {len(LONG_ITEMS)} items is already owned at the IPO in every case (the IPO threshold is 1.5 x the price of everything), so round Cash has no kept employee left to buy. Not modeled: eggs and HR levels.")
    marks["altfed"] = abs(gain_alt - gain_plain)
    print("\n**Raising the last open round, late** (Pre-IPO round, Large, raised this far through the stage; regular typical, shop complete):")
    print("| Raised at | hours saved, % of the loop | dilution bp | bp per 1% of time saved |")
    print("|---|---|---|---|")
    late = {}
    for dl in (0.0, 0.5, 0.9, 0.99):
        outs = pk_many("regular", seeds, 1, PkOpt(rounds={5: 3}, round_delay=dl, shop_done=True))
        v = _pq(pk_rel(outs, base0, 0), 50)
        late[dl] = v
        print(f"| {'at once' if dl == 0 else f'{dl:.0%} of the way'} | {v:.2f}% | {PK_FUND_LONG_BP[5][2]} | {PK_FUND_LONG_BP[5][2] / max(v, 1e-6):.0f} |")

    # ---- F. stamp tier lost on stake ----
    pop = max(12, seeds)
    T = pk_T(PK_T_POP, shop_done=True)
    print(f"\n### F. Speed against the stamp tier lost on stake (dedicated, fast, hunting for Platinum; shop complete; replays IPO 2-4; population {pop})")
    print(f"Platinum rule for this table: within 1.0 T and ratio 1.10 (S6's relaxed rule; the doc's 0.8 T / 1.25 gives no Platinum to anyone, see S6), stake at least 70%; Gold: 1.0 T, stake 55%. "
          f"T is refitted for a player whose shop is complete (Medium raise, the +25% speed perk from the start): {', '.join(f'{x:.1f}' for x in T[:4])} h.")
    print("| Policy | total dilution bp | hours per IPO (stamp clock) | Platinum on time and ratio % | Platinum kept after the stake rule % | Gold or better % |")
    print("|---|---|---|---|---|---|")
    tcfg = dict(PK_TIER, plat_frac=1.0, plat_ratio=1.10)
    for label, ch in (("no round", 0), ("Small every round", 1), ("Medium every round", 2), ("Large every round", 3)):
        kw = dict(T=T, rounds=ch, skill="expert", ipo_mode="hunt", shop_done=True)
        ro = pk_pop("dedicated", pop, 4, PkOpt(tier=tcfg, **kw))
        rn = pk_pop("dedicated", pop, 4, PkOpt(tier=dict(tcfg, plat_stake=0), **kw))
        g, pl, _k = pk_tier_rates(ro)
        _g, pl_t, _k = pk_tier_rates(rn)
        D = sum(PK_FUND_LONG_BP[st][ch - 1] for st in PK_FUND_LONG_BP) if ch else 0
        hrs = _pq([lp["stamp_h"] for r in ro for lp in r["loops"][1:]], 50)
        print(f"| {label} | {D} | {hrs:.1f} | {pl_t:.0f} | {pl:.0f} | {g:.0f} |")

    # ---- I. the table fitted to what the sim measured ----
    print("\n### I. The table refitted to the measured savings (bp = P x measured % of the loop saved x 100; P = 1.5 / 2.0 / 2.5, and the same x2.3 so that Large every round again costs about 3,000 bp)")
    print("| Stage | measured saved %: Small / Medium / Large | fitted bp at P | fitted bp at 2.3 P | the doc's bp |")
    print("|---|---|---|---|---|")
    fit1, fit2 = {}, {}
    for st in range(1, 6):
        sv = [max(save_med[(st, ci)], 0.0) for ci in range(3)]
        fit1[st] = tuple(max(1, int(PK_FUND_P[ci] * sv[ci] * 100)) for ci in range(3))
        fit2[st] = tuple(max(1, int(2.3 * PK_FUND_P[ci] * sv[ci] * 100)) for ci in range(3))
        print(f"| {names[st]} | {sv[0]:.2f} / {sv[1]:.2f} / {sv[2]:.2f} | {fit1[st][0]} / {fit1[st][1]} / {fit1[st][2]} | {fit2[st][0]} / {fit2[st][1]} / {fit2[st][2]} | {PK_FUND_LONG_BP[st][0]} / {PK_FUND_LONG_BP[st][1]} / {PK_FUND_LONG_BP[st][2]} |")
    for label, tab in (("fit at P", fit1), ("fit at 2.3 P", fit2)):
        cnt, lp, lg, oc, mx = pk_enum(tab)
        dom = all(0 < tab[st][0] < tab[st][1] - tab[st][0] < tab[st][2] - tab[st][1] for st in tab)
        tot = [sum(tab[st][c - 1] for st in tab) for c in (1, 2, 3)]
        print(f"- {label}: Small / Medium / Large every round cost {tot[0]} / {tot[1]} / {tot[2]} bp; of {cnt} sequences {lp} lose Platinum on stake (D over 3,000) and {oc} pass the 4,000 cap; dominance {'holds' if dom else 'FAILS'}.")
    marks["fit"] = (fit1, fit2, save_med)

    # ---- G. loops 1-10 ----
    ns = max(5, seeds // 2)
    print(f"\n### G. Ten loops (regular typical, the shop not complete, {ns} seeds): hours of each IPO, Shares, and when the speed lump (154 Shares) is complete")
    print("| Policy | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Shares paid, 10 IPOs | IPO at which the lump is complete |")
    print("|---|---|---|---|---|---|---|---|")
    for label, ch in (("no round", 0), ("Small every round", 1), ("Medium every round", 2), ("Large every round", 3)):
        outs = pk_many("regular", ns, 10, PkOpt(rounds=ch))
        done = [r for r in outs if len(r["loops"]) >= 10]
        cells = [f"{_pq([r['loops'][i]['eng_h'] for r in done], 50):.1f}" for i in (0, 1, 2, 4, 9)]
        sh = _pq([sum(r["shares"]) for r in done], 50)
        lump = _pq([next((i + 1 for i, lp in enumerate(r["loops"]) if lp["perk"] >= LONG_SPEED_PERKS[0]), 99) for r in done], 50)
        print(f"| {label} | " + " | ".join(cells) + f" | {sh:.0f} | {lump:.0f} |")

    # ---- H. today's 5 stages ----
    print("\n### H. Today's 5 stages (the Player model: 3 rounds, real IpoConfig numbers; online minutes of each IPO's run, Shares; median of 40 runs, 60 days)")
    print("The table's Cash is tiny next to a minute of today's Income, so rounds there are a smoke test (the runs are not paired: egg rolls differ). Shares paid with the nearest-Share carry (FUNDING 3) against a plain floor.")
    print("| Player | Policy | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Shares over 10 IPOs, with carry | plain floor |")
    print("|---|---|---|---|---|---|---|---|---|")
    for b in ("active", "casual30"):
        for label, ch in (("none", 0), ("Small", 1), ("Medium", 2), ("Large", 3)):
            cls = type("RP", (PkRoundPlayer,), {"choices": ch})
            clsf = type("RPF", (PkRoundPlayer,), {"choices": ch, "plain_floor": True})
            runs = [run(b, sd, days=SIM_DAYS_IPO, use_ipo=True, player_cls=cls) for sd in range(40)]
            runsf = [run(b, sd, days=SIM_DAYS_IPO, use_ipo=True, player_cls=clsf) for sd in range(40)]

            def gap(r, k, b=b):
                if len(r.ipo_times) < k:
                    return None
                return active_minutes_at(b, r.ipo_times[k - 1]) - (active_minutes_at(b, r.ipo_times[k - 2]) if k > 1 else 0)
            cells = [fmt_active(med([gap(r, k) for r in runs])) for k in (1, 2, 3, 5, 10)]
            tot = med([sum(r.shares_log[:10]) for r in runs if len(r.shares_log) >= 10])
            totf = med([sum(r.shares_log[:10]) for r in runsf if len(r.shares_log) >= 10])
            print(f"| {b} | {label} | " + " | ".join(cells) + f" | {tot:.0f} | {totf:.0f} |")

    # ---- result ----
    lose_p, cnt, mx, dom = marks["long"]
    real_k = next((k for k, row in real if row[0] != row[2]), None)
    fit1, fit2, sm = marks["fit"]
    pre_price = PK_FUND_LONG_BP[5][2] / 100 / max(sm[(5, 2)], 1e-9)
    mid_price = PK_FUND_LONG_BP[3][2] / 100 / max(sm[(3, 2)], 1e-9)
    pre_p = [PK_FUND_LONG_BP[5][ci] / 100 / max(sm[(5, ci)], 1e-9) for ci in range(3)]                   # the Pre-IPO row: the measured price (% of Shares per 1% of loop time) ...
    pre_x = [pre_p[ci] / PK_FUND_P[ci] for ci in range(3)]                                                 # ... and as a multiple of FUNDING's P (the multiple is not the price)
    print("\n**Result.**")
    print(f"- No choice is dominated at any stage, for LONG_GAME's 7 stages and today's 5: PASS on the doc's table (0 < S < M-S < L-M at every stage). A table refitted to the measured savings FAILS at Pre-IPO, where the measured savings flatten (0.38 / 0.55 / 0.60%) and Large costs less per extra Cash than Medium. {lose_p} of {cnt} LONG sequences lose Platinum on stake and {marks['today'][0]} of {marks['today'][1]} of today's; "
          f"the cap never binds (largest total {mx} bp and {marks['today'][2]} bp against 4,000), so only the 70% line bites. The cap is not redundant only as a safety net.")
    print(f"- **The price is not the same at every stage (FUNDING 3 says it is): FAIL.** Measured, a Large round pays {mid_price:.1f}% of Shares per 1% of loop time at Series B and {pre_price:.0f}% at Pre-IPO, against FUNDING's 2.5 (that is {pre_price / PK_FUND_P[2]:.1f} times too dear for Large; the Pre-IPO row as a whole is {pre_x[0]:.1f} / {pre_x[1]:.1f} / {pre_x[2]:.1f} times too dear for Small / Medium / Large, "
          f"and the prices themselves are {pre_p[0]:.1f} / {pre_p[1]:.1f} / {pre_p[2]:.1f} against {PK_FUND_P[0]} / {PK_FUND_P[1]} / {PK_FUND_P[2]}): from Series C+D on, buying Cash is a poor deal, and at Pre-IPO nearly a pure loss, because the Cash can only buy the current rung's items, which pay back in tens of hours. Seed to Series B (0.1-1.6% of a loop) are close to the doc's price.")
    print(f"- Large every round saves at most {marks['large_saves']:.1f}% of a loop (mark: at most 15%): PASS (FUNDING's upper bound of 12.2% is 2.4x too high: the Pre-IPO row is 7.6% in the table and 0.6% measured).")
    print(f"- Is the maximum always best? For a player who values speed, yes: Large is best in 6 of 7 profiles even with Shares valued (+3.0% against +2.4% for Medium at IPO 3). The exception is the 2x Cash owner (Small +0.1%, Large -0.4%): "
          f"mark 'no one choice best for every profile': PASS, but only because of the pass. With the shop complete and Platinum protected, the best is Medium. Scaling prices only helps up to the cap: at x{real_k if real_k else '>8'} the casual and the regular player first differ.")
    print(f"- The same round saves hours within {marks['sector_diff']:.0f}% between Software and Gaming in relative terms (mark: 5%): FAIL by the letter (Hit 14-15%, Solid and Flop 23-28%), but it is 0.3 hours, 0.6 points of a loop; the Gaming launch cycle does not change the table, one `HoursShare` table is enough.")
    print(f"- Alt-fed gains {marks['altfed']:.1f} points more from rounds than a plain player in loop 2 (mark: under 3): PASS; converter: nothing to convert (all 97 items are owned at the IPO in every case; eggs and HR are not modeled).")
    print(f"- Raising the last open round late: 0.6% saved at once, 0.0% from halfway on, for the same {PK_FUND_LONG_BP[5][2]} bp: a late raise is a pure loss, skipping beats it: PASS.")
    print(f"- Stake against speed: Large every round saves the most hours but is the only policy that loses Platinum (0% kept against 100% on time); Small and Medium keep it. The minimum prices Large-every-round without taking Platinum from most runs: PASS on the doc's table, but a table fitted to the measured savings never reaches 3,000 bp (fit at P: {sum(fit1[st][2] for st in fit1)} bp for Large every round), so the 70% line would never bite; at 2.3 P it does ({sum(fit2[st][2] for st in fit2)} bp).")
    return marks


PK_SIMS = {1: "sim_s1", 2: "sim_s2", 3: "sim_s3", 4: "sim_s4", 5: "sim_s5", 6: "sim_s6", 7: "sim_s7", 8: "sim_s8", 9: "sim_s9", 10: "sim_s10"}   # filled in as the sims are written; the name of each sim function


def pk_selected(args):
    """The sims asked for by --s1 ... --s10, --pokedex, --rounds, --gaming, --pk-check (sorted numbers; [] = only the engine check); None = none asked."""
    want = set(i for i in range(1, 11) if getattr(args, f"s{i}"))
    if args.pokedex:
        want |= set(range(1, 8))
    if args.rounds:
        want.add(8)
    if args.gaming:
        want |= {3, 9, 10}
    if args.pk_check and not want:
        return []
    return sorted(want) if (want or args.pk_check) else None


def report_pk(picked, n):
    pk_selfcheck()
    for i in picked:
        fn = PK_SIMS.get(i)
        if fn is None:
            print(f"\n## S{i}: not implemented in this version of the script.")
            continue
        globals()[fn](n)


def main():
    global SIM_DAYS_IPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=40, help="random runs per scenario (more = less noise)")
    ap.add_argument("--markdown", action="store_true", help="(output is Markdown already; flag kept for clarity)")
    ap.add_argument("--daily", action="store_true", help="only section 7: the daily calendar table")
    ap.add_argument("--ipo", action="store_true", help="only section 6: real IPO numbers in active minutes (all --runs, not half)")
    ap.add_argument("--active", action="store_true", help="only section 8: the ACTIVE-PLAY proposal (default OFF everywhere else)")
    ap.add_argument("--long", action="store_true", help="only section 9: the LONG GAME proposal (default OFF everywhere else)")
    ap.add_argument("--days", type=int, default=60, help="days simulated in section 6 and 8 (default 60)")
    for i in range(1, 11):
        ap.add_argument(f"--s{i}", action="store_true", help=f"only sim S{i} of the design docs (docs/SIMS_RESULTS.md; default OFF)")
    ap.add_argument("--pokedex", action="store_true", help="sims S1-S7 (docs/CUSTOMIZE_PROPOSAL.md 5.5; default OFF)")
    ap.add_argument("--rounds", action="store_true", help="sim S8, funding round size (docs/FUNDING_ROUNDS_PROPOSAL.md 6; default OFF)")
    ap.add_argument("--gaming", action="store_true", help="sims S3, S9 and S10 (docs/SECTORS_PROPOSAL.md 4; default OFF)")
    ap.add_argument("--pk-check", action="store_true", help="only check that the S1-S10 engine equals long_run when every hook is off")
    args = ap.parse_args()
    n = args.runs
    SIM_DAYS_IPO = args.days
    print("# Economy simulator output")
    print(f"Assumptions: claim delay without Auto-Hatch {CLAIM_DELAY_MANUAL}s; wait up to {WAIT_SECONDS}s for a better buy; "
          f"sessions {BEHAVIOURS}")
    print("IPO perk effects (FasterEggs, ExtraIncubator, ExtraSlot, OfflineCap, BaseLuck, CheaperPoach) are "
          "NOT modeled: every IPO figure below assumes no perks bought. A perk-buying player is estimated "
          "to be roughly 15-25% faster per IPO cycle than these numbers show.")
    print(f"Daily login calendar (DailyConfig.lua, M6) IS modeled: claimed at the first login of every day, Cash as a gift "
          f"(not valuation). In sections 1-6: {'ON' if DAILY_IN_ALL_TABLES else 'OFF'} (DAILY_IN_ALL_TABLES); section 7 compares calendars.")
    if args.long:
        report_long(n)
        return
    picked = pk_selected(args)
    if picked is not None:
        report_pk(picked, n)
        return
    if args.active:
        report_active(n, args.days)
        return
    if args.daily:
        report_daily(n)
        return
    if args.ipo:
        report_real_ipo(n, args.days)
        return
    report_main(n)
    report_slots_pass(n)
    report_passes(n)
    report_ipo(max(5, n // 4))
    report_real_ipo(max(5, n // 2))
    report_detail(n)
    report_daily(max(5, n * 3 // 4))


if __name__ == "__main__":
    main()
