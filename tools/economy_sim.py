#!/usr/bin/env python3
"""Economy simulator for "Build your Startup!" (standard library only).

Run:   python tools/economy_sim.py            (prints all tables, takes ~1 minute)
       python tools/economy_sim.py --runs 10  (faster, noisier)
       python tools/economy_sim.py --markdown (prints the tables as Markdown for docs/ECONOMY.md)
       python tools/economy_sim.py --daily    (only section 7, the daily calendar table)

It reads NOTHING from the game: every number is copied by hand into the CONFIG block below.
If you change a .lua config, update this block too. It never changes any game number.
The model is event-driven (no fixed time step), so a 7-day run takes a few milliseconds.

The 7-day login calendar (DailyConfig.lua, milestone 6) IS modeled: see the DAILY_* block and
section 7. A simulated player claims at the first login of every day (they never miss one, the
worst case for the economy). Calendar Cash is a gift: it goes to Cash only, never to the
valuation, exactly like DailyServer; claim_daily asserts it. Sections 1-6 run without the
calendar (DAILY_IN_ALL_TABLES = False) so they stay comparable with docs/ECONOMY.md.
"""

import argparse
import random
import statistics

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
IPO_SHARES_GROWTH = 0.3             # IpoConfig.SharesGrowthPerIpo
IPO_SHARES_RATIO_CAP = 4            # IpoConfig.SharesRatioCap
IPO_SHARES_EXPONENT = 0.5           # IpoConfig.SharesExponent
SHAREHOLDER_MULT = 2                # ShopConfig Passes.Shareholder: 2x Shares per IPO (199 R$)
IPO_COOLDOWN_SECONDS = 60           # IpoConfig.CooldownSeconds (not modeled: every gap between IPOs is far longer)
IPO_PERK_COSTS = {                  # IpoConfig.Perks: Shares for each level, per perk (total = everything in the IPO shop)
    "FasterEggs": [5, 10, 20, 35, 50], "ExtraIncubator": [15, 40], "ExtraSlot": [10, 25, 50],
    "OfflineCap": [5, 10, 20, 35], "BaseLuck": [5, 10, 20, 35, 50], "CheaperPoach": [5, 10, 15, 20, 25],
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


class Player:
    def __init__(self, rng, double_cash=False, vip=False, extra_slots=False, auto_hatch=False, luck_boost=False, shareholder=False,
                 daily=None, daily_cash_counts=False):
        self.rng = rng
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

    def income(self):
        return self.base_income() * self.mult_pass * self.ipo_mult()

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
            cash = max(DAILY_MIN_CASH, int(self.income() * 60 * minutes))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=40, help="random runs per scenario (more = less noise)")
    ap.add_argument("--markdown", action="store_true", help="(output is Markdown already; flag kept for clarity)")
    ap.add_argument("--daily", action="store_true", help="only section 7: the daily calendar table")
    args = ap.parse_args()
    n = args.runs
    print("# Economy simulator output")
    print(f"Assumptions: claim delay without Auto-Hatch {CLAIM_DELAY_MANUAL}s; wait up to {WAIT_SECONDS}s for a better buy; "
          f"sessions {BEHAVIOURS}")
    print("IPO perk effects (FasterEggs, ExtraIncubator, ExtraSlot, OfflineCap, BaseLuck, CheaperPoach) are "
          "NOT modeled: every IPO figure below assumes no perks bought. A perk-buying player is estimated "
          "to be roughly 15-25% faster per IPO cycle than these numbers show.")
    print(f"Daily login calendar (DailyConfig.lua, M6) IS modeled: claimed at the first login of every day, Cash as a gift "
          f"(not valuation). In sections 1-6: {'ON' if DAILY_IN_ALL_TABLES else 'OFF'} (DAILY_IN_ALL_TABLES); section 7 compares calendars.")
    if args.daily:
        report_daily(n)
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
