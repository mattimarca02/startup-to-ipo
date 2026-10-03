#!/usr/bin/env python3
"""Economy simulator for "Build your Startup!" (standard library only).

Run:   python tools/economy_sim.py            (prints all tables, takes ~1 minute)
       python tools/economy_sim.py --runs 10  (faster, noisier)
       python tools/economy_sim.py --markdown (prints the tables as Markdown for docs/ECONOMY.md)
       python tools/economy_sim.py --daily    (only section 7, the daily calendar table)
       python tools/economy_sim.py --active   (only section 8, the ACTIVE-PLAY proposal; default OFF everywhere else)
       python tools/economy_sim.py --long     (only section 9, the LONG-GAME proposal: 55 active hours to the first IPO; default OFF)

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


def _simulate_tasks(n, fam, level, stage, skill, waves, rng):
    """Net Income-seconds per second the tasks add for ONE roster, and how busy the founder is. n = employees,
    fam = role family -> number of employees, stage = funding stage (first run only, None after the 1st IPO)."""
    prof = ACTIVE_SKILLS[skill]
    H = ACTIVE_HORIZON
    rows = [t for t in ACTIVE_TASKS if t["wave"] in waves and (stage is None or t["unlock"] <= stage)]
    rate = min(1.4, 1 + 0.02 * level)               # harder: tasks come a bit faster ...
    lim_scale = max(0.65, 1 - 0.03 * level)         # ... with less time ...
    p_drop = 0.008 * level                          # ... and are a little harder to get right
    arrivals = []
    for i, t in enumerate(rows):
        scale = 1.0 / ((1 + t["demand"] * n) * rate)   # more hires = more demand = shorter gaps
        clock = rng.uniform(0, t["every"][1]) * scale
        while clock < H:
            arrivals.append((clock, i))
            clock += rng.uniform(*t["every"]) * scale
    arrivals.sort()
    share = [min(ACTIVE_AUTO_CAP, 1 - (1 - t["auto"]) ** fam.get(t["fam"], 0)) if t["fam"] and t["auto"] > 0 else 0.0 for t in rows]
    st = {"net": 0.0, "busy": 0.0, "bucket": float(ACTIVE_BUDGET_BANK), "bt": 0.0, "streak": 0}

    def pay(amount, now):
        """A reward goes through the budget; a loss (negative) is taken as it is."""
        if amount <= 0:
            st["net"] += amount
            return
        st["bucket"] = min(ACTIVE_BUDGET_BANK, st["bucket"] + ACTIVE_BUDGET_RATE * (now - st["bt"]))
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
    return {"f": st["net"] / H, "busy": min(1.0, st["busy"] / H)}


def active_factor(roster, stage, ipos, skill, waves):
    """{"f": extra Income as a fraction of Income, "busy": share of the time the founder is busy} for this team."""
    if not roster or skill in (None, "ignore"):
        return ACTIVE_NONE
    fam = {}
    for inc in roster:
        for f, w in ACTIVE_ROLE_FAMILY.get(inc, {"ops": 1}).items():
            fam[f] = fam.get(f, 0) + w
    level = stage + min(ipos, ACTIVE_LEVEL_IPO_CAP)
    first_stage = stage if ipos == 0 else None
    key = (len(roster), tuple(sorted((f, round(w * 2) / 2) for f, w in fam.items())), level, first_stage, skill, tuple(waves))
    hit = _ACTIVE_CACHE.get(key)
    if hit is None:
        hit = _simulate_tasks(len(roster), dict(key[1]), level, first_stage, skill, waves, random.Random(zlib.crc32(repr(key).encode())))
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
    p = Player(rng, daily=daily or None, daily_cash_counts=daily_cash_counts, **passes)
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
# The IPO is the last thing a player reaches: first IPO after ~55-60 ACTIVE online hours, every later loop 55+ h.
# Model: a ladder of LONG_STAGES. Each stage has an income CEILING (what its office can hold) and the player buys
# LONG_ITEMS_PER_STAGE items (offices, upgrades, hires) that lift Income from the last ceiling to this one. Prices and
# valuation thresholds are CALIBRATED (long_ladder) so a "regular" player who is always engaged hits the target hours:
# the sim does not prove the targets, it shows what happens to the OTHER players, rules and loops. Valuation counts only
# Cash earned while the player is engaged (online and acting); Cash from away time (10% of active pay, 2 h cap) counts 10% toward it.
# =============================================================================
LONG_STAGES = [                     # (name, target active hours inside the stage in the first run, income ceiling in Cash/s)
    ("Garage", 1.5, 6), ("Seed", 4, 20), ("Series A", 6.5, 65), ("Series B", 9, 210),
    ("Series C", 11, 700), ("Series D", 13, 2300), ("Pre-IPO", 15, 7500),
]                                   # the 8th rung is IPO-ready: the valuation at the end of Pre-IPO (target 60 h in total with no away pay; about 56 h for the typical player with it)
LONG_ITEMS_PER_STAGE = 10           # priced purchases per stage (office pieces, upgrades, hires), after the stage opens
LONG_START_INCOME = 2.0             # Cash/s of an empty garage
LONG_BUY_FRACTION = 0.6             # the stage's items are all bought after this share of the stage's target time
LONG_ROSTERS = [[3], [3, 7], [3, 7, 8], [3, 7, 8, 20], [3, 7, 8, 20, 24], [3, 7, 8, 20, 24, 50], [3, 7, 8, 9, 20, 24, 50, 60]]
LONG_LOOP_GROWTH = 0.05             # prices and valuation thresholds of loop L = multiplier x carry x (1 + this) ^ L
LONG_CARRY = 1.35                   # kept employees refill the new offices fast: Income x this from the 2nd run on
LONG_AWAY = (0.10, 2 * 3600, 0.10)  # NEW rule: away pay = 10% of the ACTIVE pay you left with, at most 2 h per return, 10% of it counts toward valuation
LONG_AWAY_OLD = (0.50, 8 * 3600, 1.0)   # today: 50% of passive Income, 8 h, 100% valuation (passive only: no task bonus)
LONG_SHARES = (20, 0.25, 1.5, 0.5)  # Shares = base x (1 + growth x IPOs done) x min(ratio, cap) ^ exponent (x2 Shareholder pass)
LONG_SHOP = {                       # PROPOSED IPO shop (same keys and levels as IpoConfig.Perks, re-priced; the sim only uses the totals)
    "FasterEggs": [1, 2, 3, 5, 7, 10, 16], "ExtraIncubator": [4, 8], "ExtraSlot": [4, 8, 18],
    "BaseLuck": [1, 2, 3, 5, 7, 10, 16, 24], "OfflineCap": [2, 4, 7, 12], "CheaperPoach": [2, 3, 4, 6, 8, 11, 15, 20, 28, 40],
}
LONG_PRESTIGE_WING = 434            # new cosmetic / prestige items (office skins, creature hats, titles): Shares, all cosmetic
LONG_SPEED_KEYS = ("FasterEggs", "ExtraIncubator", "ExtraSlot", "BaseLuck")   # the perks that move the clock
LONG_SPEED_PERKS = (sum(sum(LONG_SHOP[k]) for k in LONG_SPEED_KEYS), 0.25)   # their whole price (154 Shares) is worth at most +25% Income (an estimate)
LONG_DT = 20.0                      # seconds per step while a session runs
LONG_PLAYERS = {                    # (sessions per day as (start hour, minutes), days of the week played, chance a planned session happens)
    "dedicated": ([(0, 60), (12, 60)], range(7), 0.95),    # 2 h a day, 14 h a week
    "regular": ([(0, 60)], range(7), 0.90),                # 1 h a day, ~6 h a week
    "casual": ([(0, 60)], (0, 2, 5), 0.85),                # 3 sessions a week, ~2.5 h a week
    "check-in": ([(0, 1)], range(7), 0.90),                # 1 minute a day: collects the away Cash and leaves
}


def _long_f(stage, loop, skill):
    return active_factor(LONG_ROSTERS[stage], min(stage, 4), loop, skill, (1, 2, 3))["f"]


def long_ladder():
    """Calibrated rungs: [(name, target h, ceiling, payback P in seconds, valuation earned inside the rung, f, r, previous ceiling)]
    and the cumulative valuation thresholds (entering rung i needs cum[i]; cum[-1] = IPO-ready), all at loop 0 prices.
    The payback P makes a stage's items all bought after LONG_BUY_FRACTION of its target time; the thresholds are then
    read off a reference player (always engaged, no away pay, average task bonus) at the target times, so that player hits
    the targets by construction."""
    rows, prev, k = [], LONG_START_INCOME, LONG_ITEMS_PER_STAGE
    for s, (name, hours, ceiling) in enumerate(LONG_STAGES):
        f = _long_f(s, 0, "typical")
        r = (ceiling / prev) ** (1.0 / k)
        pay = LONG_BUY_FRACTION * hours * 3600 * (1 + f) / (k * (r - 1))
        rows.append([name, hours, ceiling, pay, 0.0, f, r, prev])
        prev = ceiling
    inc, pay_of = long_items(rows)
    cum, stage, owned, cash, val, t, edge = [0.0], 0, 0, 0.0, 0.0, 0.0, 0.0
    ends = []
    for row in rows:
        edge += row[1] * 3600
        ends.append(edge)
    dt = 10.0
    while stage < len(rows):
        gain = inc[owned] * (1 + rows[stage][5]) * dt
        cash += gain
        val += gain
        t += dt
        while owned < len(pay_of) and owned // k <= stage:
            cost = pay_of[owned] * (inc[owned + 1] - inc[owned])
            if cash < cost:
                break
            cash -= cost
            owned += 1
        if t >= ends[stage]:
            cum.append(val)
            rows[stage][4] = cum[-1] - cum[-2]
            stage += 1
    return [tuple(r) for r in rows], cum


def long_items(rows):
    """Income after buying item j (inc[0] = empty garage) and the payback of each item, over all rungs."""
    inc, pay_of = [LONG_START_INCOME], []
    for row in rows:
        for i in range(1, LONG_ITEMS_PER_STAGE + 1):
            inc.append(row[7] * row[6] ** i)
            pay_of.append(row[3])
    return inc, pay_of


def long_scale(loop, growth):
    """Prices and thresholds of a run after `loop` IPOs (also the Income multiplier x carry, which cancels out)."""
    if loop <= 0:
        return 1.0
    return (1 + IPO_BONUS_PER_IPO * loop ** IPO_BONUS_EXPONENT) * LONG_CARRY * (1 + growth) ** loop


def long_run(kind, seed, loops=1, away=LONG_AWAY, growth=LONG_LOOP_GROWTH, skill="typical", cash_mult=1.0, valuation_at_base=True,
             shareholder=False, max_days=1100):
    """One player until `loops` IPOs. Returns dict(stage_h = [[active hours when each stage opened] per loop], ipo_h, ipo_day,
    shares, away_share = share of the valuation that came from away time)."""
    rng = random.Random(seed * 7919 + zlib.crc32(kind.encode()))
    sessions, days, chance = LONG_PLAYERS[kind]
    rows, cum = long_ladder()
    k = LONG_ITEMS_PER_STAGE
    inc, pay_of = long_items(rows)
    n_items = len(pay_of)
    loop, owned, cash, val, active_s = 0, 0, 0.0, 0.0, 0.0
    stage, shares, spent_speed = 0, 0, 0
    out = {"stage_h": [[0.0]], "ipo_h": [], "ipo_day": [], "shares": [], "away_val": 0.0, "val_total": 0.0}
    last_end = None
    base_ratio = 1.0 if valuation_at_base else cash_mult   # the Cash pass only multiplies spendable Cash unless the valuation counts it too
    speed = 1.0
    for day in range(max_days):
        if day % 7 not in days:
            continue
        for start_h, minutes in sessions:
            if rng.random() > chance:
                continue
            length = max(1, minutes * rng.uniform(0.7, 1.3)) * 60
            s_start = day * DAY + start_h * 3600
            sc = long_scale(loop, growth)
            m_inc = (long_scale(loop, 0.0) if loop else 1.0)
            if last_end is not None and away[0] > 0:
                gap = min(s_start - last_end, away[1])
                if away is LONG_AWAY_OLD:
                    pay_away = gap * away[0] * inc[owned] * m_inc * speed
                else:
                    pay_away = gap * away[0] * inc[owned] * m_inc * speed * (1 + _long_f(stage, loop, skill))
                cash += pay_away * cash_mult
                credit = pay_away * away[2] * base_ratio
                val += credit
                out["away_val"] += credit
            t = 0.0
            while t < length:
                dt = min(LONG_DT, length - t)
                f = _long_f(stage, loop, skill) * rng.uniform(0.85, 1.15)
                income = inc[owned] * m_inc * speed
                gain = income * (1 + f) * dt
                cash += gain * cash_mult
                val += gain * base_ratio
                active_s += dt
                t += dt
                while owned < n_items:
                    s_of = owned // k
                    if s_of > stage:
                        break
                    cost = pay_of[owned] * (inc[owned + 1] - inc[owned]) * sc
                    if cash < cost:
                        break
                    cash -= cost
                    owned += 1
                while stage < len(LONG_STAGES) and val >= cum[stage + 1] * sc:
                    stage += 1
                    if stage < len(LONG_STAGES):
                        out["stage_h"][-1].append(active_s / 3600)
                if stage >= len(LONG_STAGES):          # IPO-ready: the player goes public right away
                    ratio = min(LONG_SHARES[2], val / (cum[-1] * sc))
                    gained = int(LONG_SHARES[0] * (1 + LONG_SHARES[1] * loop) * ratio ** LONG_SHARES[3] * (2 if shareholder else 1))
                    shares += gained
                    out["shares"].append(gained)
                    out["ipo_h"].append(active_s / 3600)
                    out["ipo_day"].append((s_start + t) / DAY)
                    out["val_total"] += val
                    room = max(0, LONG_SPEED_PERKS[0] - spent_speed)
                    buy = min(room, shares)
                    spent_speed += buy
                    shares -= buy
                    speed = 1 + LONG_SPEED_PERKS[1] * spent_speed / LONG_SPEED_PERKS[0]
                    loop += 1
                    owned, cash, val, stage = 0, 0.0, 0.0, 0
                    out["stage_h"].append([active_s / 3600])
                    if loop >= loops:
                        out["away_share"] = out["away_val"] / max(out["val_total"], 1e-9)
                        return out
                    sc = long_scale(loop, growth)
                    m_inc = long_scale(loop, 0.0)
            last_end = s_start + length
    out["away_share"] = out["away_val"] / max(val + out["val_total"], 1e-9)
    return out


def _long_many(kind, n, **kw):
    return [long_run(kind, seed, **kw) for seed in range(n)]


def _fmt_h(v):
    return "never" if v is None else f"{v:.1f} h"


def report_long(n):
    """Section 9: the long game. Only with --long."""
    rows, cum = long_ladder()
    print(f"\n## 9. LONG GAME (proposal, default OFF), median of {n} runs, minutes/hours are ACTIVE online time (engaged)")
    print("### 9a. Calibrated ladder (loop 0 prices; thresholds are what the regular player needs to hit the target hours)")
    print("| Rung | Target h in stage | Cumulative h | Income ceiling /s | Payback of an item (active h) | Valuation to enter next rung | Task bonus f |")
    print("|---|---|---|---|---|---|---|")
    tot = 0.0
    for i, (name, hours, ceiling, pay, earned, f, r, prev) in enumerate(rows):
        tot += hours
        nxt = LONG_STAGES[i + 1][0] if i + 1 < len(LONG_STAGES) else "IPO-ready"
        print(f"| {name} | {hours:g} | {tot:g} | {ceiling:,.0f} | {pay / 3600:.1f} | {cum[i + 1]:,.0f} ({nxt}) | x{1 + f:.2f} |")
    print("\n### 9b. Active hours to each rung and IPO 1, three players (new away rule), and the weeks that takes")
    head = "| Player (played) | " + " | ".join(s[0] for s in LONG_STAGES[1:]) + " | IPO-ready (IPO 1) | Weeks to IPO 1 | Shares |"
    print(head)
    print("|" + "---|" * (len(LONG_STAGES) + 4))
    for kind in ("dedicated", "regular", "casual", "check-in"):
        runs = _long_many(kind, n if kind != "check-in" else max(5, n // 4), max_days=1100)
        done = [r for r in runs if r["ipo_h"]]
        cells = []
        for si in range(1, len(LONG_STAGES)):
            vals = [r["stage_h"][0][si] for r in runs if len(r["stage_h"][0]) > si]
            cells.append(_fmt_h(med(vals)) if len(vals) >= len(runs) / 2 else "not in 3 y")
        ipo_h = med([r["ipo_h"][0] for r in done]) if len(done) >= len(runs) / 2 else None
        wk = med([r["ipo_day"][0] / 7 for r in done]) if ipo_h is not None else None
        sh = med([r["shares"][0] for r in done]) if ipo_h is not None else None
        label = {"dedicated": "dedicated (2 h/day)", "regular": "regular (1 h/day)", "casual": "casual (3 x 1 h/week)", "check-in": "check-in only (1 min/day)"}[kind]
        print(f"| {label} | " + " | ".join(cells) + f" | {_fmt_h(ipo_h)} | {'-' if wk is None else f'{wk:.0f}'} | {'-' if sh is None else f'{sh:.0f}'} |")
    ex = _long_many("regular", n, skill="expert")
    print(f"| regular, expert at tasks | (same ladder) | | | | | | {_fmt_h(med([r['ipo_h'][0] for r in ex]))} | {med([r['ipo_day'][0] / 7 for r in ex]):.0f} | {med([r['shares'][0] for r in ex]):.0f} |")
    print("\n### 9c. Offline rule: what decides the IPO (regular player, active hours to IPO 1 and share of valuation that came from away time)")
    print("| Rule | Active h to IPO 1 | Wall weeks | Valuation from away |")
    print("|---|---|---|---|")
    for label, rule in (("no away pay at all", (0.0, 0, 0.0)), ("NEW: 10% of active pay, 2 h cap, 10% counts", LONG_AWAY),
                        ("NEW but 25% counts", (0.10, 2 * 3600, 0.25)), ("NEW but 100% counts", (0.10, 2 * 3600, 1.0)), ("TODAY: 50% of passive, 8 h cap, 100% counts", LONG_AWAY_OLD)):
        for kind in ("regular", "check-in"):
            runs = _long_many(kind, n if kind == "regular" else max(5, n // 4), away=rule, max_days=1100)
            done = [r for r in runs if r["ipo_h"]]
            h = med([r["ipo_h"][0] for r in done]) if len(done) >= len(runs) / 2 else None
            wk = med([r["ipo_day"][0] / 7 for r in done]) if h is not None else None
            share = med([r["away_share"] for r in runs])
            print(f"| {label}, {kind} | {_fmt_h(h)} | {'-' if wk is None else f'{wk:.0f}'} | {share:.0%} |")
    print("\n### 9d. Cash pass (x2): does it still halve the first IPO?")
    print("| Regular player | Active h to IPO 1 |")
    print("|---|---|")
    for label, kw in (("no pass", {}), ("2x Cash pass, valuation counts base Cash (proposed)", {"cash_mult": 2.0, "valuation_at_base": True}),
                      ("2x Cash pass, valuation counts doubled Cash (today)", {"cash_mult": 2.0, "valuation_at_base": False})):
        runs = _long_many("regular", n, **kw)
        print(f"| {label} | {_fmt_h(med([r['ipo_h'][0] for r in runs]))} |")
    print("\n### 9e. Loops: active hours per loop and Shares (3 loops)")
    print("| Player | Thresholds grow | Loop 1 | Loop 2 | Loop 3 | Shares IPO 1 / 2 / 3 (no pass) | with Shareholder pass |")
    print("|---|---|---|---|---|---|---|")
    for kind in ("dedicated", "regular"):
        for growth in (0.0, LONG_LOOP_GROWTH, 0.10):
            runs = _long_many(kind, max(5, n // 2), loops=3, growth=growth)
            pr = _long_many(kind, max(5, n // 4), loops=3, growth=growth, shareholder=True)
            def loop_h(rs, i):
                vals = [(r["ipo_h"][i] - (r["ipo_h"][i - 1] if i else 0)) for r in rs if len(r["ipo_h"]) > i]
                return _fmt_h(med(vals))
            def shr(rs):
                return " / ".join(f"{med([r['shares'][i] for r in rs if len(r['shares']) > i]):.0f}" for i in range(3))
            print(f"| {kind} | +{growth:.0%} per loop | {loop_h(runs, 0)} | {loop_h(runs, 1)} | {loop_h(runs, 2)} | {shr(runs)} | {shr(pr)} |")
    print("\n### 9f. Ten loops (+5% per loop, Shareholder pass in brackets): active hours and wall weeks to IPO N, Shares owned in total, no spending limit")
    print("| Player | IPO 1 | IPO 2 | IPO 3 | IPO 5 | IPO 10 | Shares after IPO 1 / 2 / 5 / 10 |")
    print("|---|---|---|---|---|---|---|")
    for kind in ("dedicated", "regular", "casual"):
        runs = _long_many(kind, max(5, n // 6), loops=10, max_days=4000)
        pr = _long_many(kind, max(5, n // 6), loops=10, max_days=4000, shareholder=True)
        cells = []
        for k in (1, 2, 3, 5, 10):
            h = med([r["ipo_h"][k - 1] for r in runs if len(r["ipo_h"]) >= k])
            w = med([r["ipo_day"][k - 1] / 7 for r in runs if len(r["ipo_day"]) >= k])
            cells.append(f"{h:.0f} h / {w:.0f} wk" if h is not None else "-")
        def tot(rs, k):
            return med([sum(r["shares"][:k]) for r in rs if len(r["shares"]) >= k])
        print(f"| {kind} | " + " | ".join(cells) + " | " + " / ".join(f"{tot(runs, k):.0f} ({tot(pr, k):.0f})" for k in (1, 2, 5, 10)) + " |")
    core = sum(sum(c) for c in LONG_SHOP.values())
    print(f"\nProposed shop: core perks {core} Shares (speed perks {LONG_SPEED_PERKS[0]}), prestige wing {LONG_PRESTIGE_WING}, total {core + LONG_PRESTIGE_WING} (today {sum(sum(c) for c in IPO_PERK_COSTS.values())}).")
    print("\nNot measured: how fun the tasks are at hour 40, whether the content exists (docs/LONG_GAME_PROPOSAL.md section 2), "
          "the real task Income (a Monte Carlo with a fixed roster per rung, 8 hires at most, not the real team of 20 desks), egg timers, "
          "luck, poaching, perks beyond a +25% speed lump (an estimate), sessions that run longer than planned, players who leave, Investor Day, and "
          "anything that depends on people (retention, friends, social pull). The thresholds are fitted to the regular player, so 'regular = about 57 h' is the target, not a result.")



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
