"""First-hour model for docs/GAMEPLAY_FIRST_HOUR_PROPOSAL.md (design only; standard library only; deterministic).

Run:   python3 tools/first_hour_model.py             prints every table the proposal quotes
       python3 tools/first_hour_model.py --check     exit 1 if a table in the doc or a copied constant differs
       python3 tools/first_hour_model.py --previous  sessions 1-2's models A, B, D, G and session 2's x3.1 Garage, reproduced
       python3 tools/first_hour_model.py --fit       re-runs the E1 Garage fit (6 s) and compares it with E1_LEVELS

Why a separate model: tools/economy_sim.py (never edited from here) has no free egg, no customer calls and no
Day 1 gift, and its typical player is not a brand-new one. This file follows ONE new player second by second,
with those three things and human delays. It imports nothing from the repo: its constants are copied from the
code (main e3c9e67) and the proposals, each with its source, and `--check` re-reads the sources marked (checked)
and fails if one drifted.

ASSUMPTIONS (estimates, not measured; every number printed is an estimate or a placeholder):
 1. Loading ends (data.ready) at 0:04; Income starts then (TycoonCore income loop, 1 s ticks).
 2. The player gets the free Desk at 0:30 (finds SHOP > Office). Reading the sector picker is not modelled.
 3. The free egg is granted at 0:02 (inside setupPlayer, before ready) and hatches 60 s later.
 4. A ready egg is hatched 20 s after it is ready (economy_sim uses 20 s too).
 5. A purchase happens 5 s after it becomes affordable (reading the card, tapping).
 6. 80% of calls are answered, the rest expire and reset the chain. One random stream, seed 1.
 7. Calls (task-needs-desk): the first rings a normal gap after the Desk; gap = U(20, 40) / min(2, 1 + 0.08 x hires);
    pay = 7 s of Income x min(2, 1 + 0.1 x the chain before this answer). Team auto-answers (20% per sales hire)
    and the difficulty speed-up (1 in the Garage before any IPO) are left out.
 8. A Garage Egg hire pays the Garage Egg's average Income with today's odds (70/25/5): $4.97/s; the free egg too.
    The launch Garage Egg's odds are not designed yet.
 9. One hire per desk (LONG PR 3); the free hire takes Desk 1, so Desk 2 and Desk 3 each carry one bought egg.
10. The Day 1 gift (5 min of Income, at least $300) is claimed 10 s after the third hire (tutorial step 6 at the
    first pause after minute 10). Cash only, never valuation (DailyServer).
11. Valuation = all Cash earned from Income and calls. In the first hour the LONG daily cap (3 engaged hours) and the
    Garage task budget (0.85 s of Income per second) never bind, so neither is modelled.
12. D1 keeps LONG's buying order. E1 (owner, 2026-10-06) splits the Whiteboard and the Neon Logo into levels I and II,
    each with half the Income (+$20, +$20, +$60, +$60: the Garage's total Income is unchanged), like LONG's Series C+D
    (economy_sim.py:1064). Their four prices and the Garage milestone shares 2-4 are placeholders found by `--fit`:
    Seed between 1:30:00 and 1:31:00, milestone 1 by 10:00, no wait over 6:30 in minutes 0-20, then the waits after
    20:00 as short as possible (largest first). Seed's valuation follows the prices (LONG_K x everything in the Garage),
    so every later rung's entry moves with them. The real re-fit is economy_sim.py --long's job (build order item 9).
13. "Longest wait" = the longest time between two consecutive events (purchase, hire, stage, milestone), from 0:00 to
    the last event before 20:00. Calls and Cash ticks are not events.
14. Prices of later IPO runs scale with LONG's StageScale; every price here is the first run's.
"""
import argparse
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "GAMEPLAY_FIRST_HOUR_PROPOSAL.md"
BEGIN, END = "<!-- first-hour-model:begin -->", "<!-- first-hour-model:end -->"

# ---------------------------------------------------------------------------------------------------------------
# Constants copied from the code (main e3c9e67) and the proposals. (checked) = --check re-reads the source.
# ---------------------------------------------------------------------------------------------------------------
TODAY_UPGRADES = [("Desk", 0, 1), ("Coffee Machine", 25, 2), ("Laptop", 100, 5), ("Server Rack", 400, 15),
                  ("Whiteboard", 1500, 40), ("Neon Logo", 5000, 120)]          # TycoonCore.lua:66-71 (checked)
GARAGE_EGG = {"price": 250, "hatch": 60, "odds": {"Common": 70, "Uncommon": 25, "Rare": 5}}  # CreatureConfig.lua:25-31 (checked)
GARAGE_INCOMES = {"Common": (2, 3, 3), "Uncommon": (7, 8, 9), "Rare": (20, 24)}  # CreatureConfig.Creatures by rarity
GARAGE_EGG_EV = sum(GARAGE_EGG["odds"][r] / 100 * sum(v) / len(v) for r, v in GARAGE_INCOMES.items())  # 4.97/s
TODAY_STAGES = [("Seed", 1800), ("Series A", 6300), ("Series B", 23400), ("IPO-ready", 81000)]  # IpoConfig.lua:19-22 (checked)
CALL = {"every": (20, 40), "seconds": 7, "step": 0.1, "max": 2.0, "demand": 0.08, "cap": 2.0}  # TaskConfig.lua:53-55, 62 (checked)
DAY1 = {"seconds": 5 * 60, "min": 300}                                          # DailyConfig.lua:24, 38 (checked)
POACH_TODAY = {"seconds": 300, "min": 500}                                      # CreatureConfig.lua:117-118 (checked)
BASE_CHANCE = {"Common": 0.6, "Uncommon": 0.5, "Rare": 0.4, "Epic": 0.3}        # CreatureConfig.lua:114 (checked)
NEGOTIATION = (8, 10)                                                           # CreatureConfig.lua:119 (checked)
ATTACKER_COOLDOWN = 30                                                          # CreatureConfig.lua:120 (checked); from the end of a negotiation, PoachServer.lua:391
HEADHUNTER_TODAY = 0.1                                                          # ShopConfig.lua:79 (checked); added to the chance, CreatureConfig.lua:410

LONG_K = 1.5                                                                    # economy_sim.py LONG_K (checked)
LONG_RUNGS = ["Garage", "Seed", "Series A", "Series B", "Series C+D", "Pre-IPO"]
LONG_RUNG_SUMS = [131400, 4200000, 20660000, 76700000, 523200000, 618000000]    # LONG_ITEMS prices per rung (checked)
LONG_GARAGE_PLANNED = {"Coffee Machine": 1100, "egg": 2300, "Laptop": 4200, "Desk 2": 3600}  # LONG_ITEMS rung 0 (checked)
LONG_EGG_TIERS = [  # (tier, egg price at launch, the hire LONG prices that egg at, its Income): LG:40-47, LONG_ITEMS
    ("Garage", 400, "Coding Cat", 3),          # D1 placeholder ($2,300 in LONG, $250 today)
    ("Startup", 310000, "Sales Shark", 20),
    ("Scale-up", 1400000, "Ledger Llama", 60),
    ("Unicorn", 7100000, "Venture Dragon", 175),
    ("Decacorn", 26000000, "Compliance Cobra", 300),
    ("Blue-Chip", 70000000, "Brand Badger", 540),
]
HIRES = [  # (creature, Income, rarity today (None = new type, rarity not set), home egg tier: economy_sim LONG_HIRE_TYPES)
    ("Coffee Capybara", 2, "Common", "Garage"), ("Coding Cat", 3, "Common", "Garage"),
    ("Pixel Pigeon", 3, "Common", "Garage"), ("Hustle Hamster", 7, "Uncommon", "Garage"),
    ("Bug Beetle", 8, "Uncommon", "Garage"), ("Memo Mole", 9, "Uncommon", "Garage"),
    ("Sales Shark", 20, "Rare", "Startup"), ("Pitch Parrot", 24, "Rare", "Startup"),
    ("Server Sloth", 50, "Epic", "Startup"), ("Ledger Llama", 60, "Epic", "Scale-up"),
    ("Unicorn CEO", 150, "Legendary", "Scale-up"), ("Venture Dragon", 175, "Legendary", "Scale-up"),
    ("Growth Gecko", 220, None, "Unicorn"), ("Compliance Cobra", 300, None, "Unicorn"),
    ("Platform Panda", 380, None, "Decacorn"), ("Closer Condor", 460, None, "Decacorn"),
    ("Brand Badger", 540, None, "Blue-Chip"), ("Board Bison", 620, None, "Blue-Chip"),
]

# ---------------------------------------------------------------------------------------------------------------
# Assumptions (estimates) and the owner's decisions as placeholders
# ---------------------------------------------------------------------------------------------------------------
T_READY, T_DESK, NOTICE, REACT, ANSWER_RATE, SEED, GIFT_DELAY = 4, 30, 20, 5, 0.8, 1, 10

D1_LADDER = [  # (name, price, kind, Income; None = a Garage Egg hire at GARAGE_EGG_EV): D1 placeholders in buying order
    ("Coffee Machine", 150, "up", 2), ("Laptop", 800, "up", 5), ("Desk 2", 1000, "desk", 0), ("Garage Egg", 400, "egg", None),
    ("Desk 3", 5000, "desk", 0), ("Garage Egg", 400, "egg", None), ("Server Rack", 13000, "up", 15),
    ("Whiteboard", 28000, "up", 40), ("Neon Logo", 72000, "up", 120),
]
D1_FIT = ("Whiteboard", "Neon Logo")       # session 2 scaled these two; E1 splits them (assumption 12)
GARAGE_TARGET = 90 * 60                    # LONG's fitted Garage: 1.5 h (LG:7)
E1_LEVELS = [("Whiteboard I", 30000, 20), ("Whiteboard II", 55000, 20),         # E1 placeholders, from --fit
             ("Neon Logo I", 120000, 60), ("Neon Logo II", 220000, 60)]
E1_SLOTS = "BBMBMBMS"   # the fit's target order after the Server Rack: B = a level bought, M = milestones 2-4, S = Seed

MILESTONE_SHARES = {"Garage": (0.01, 0.24, 0.49, 0.84), "other": (0.20, 0.40, 0.60, 0.80)}  # D2: share of the rung's valuation distance
# Garage: milestone 1 comes before 10:00, milestones 2-4 sit in the middle of the waits after the Server Rack (--fit);
# the other rungs use LONG 4(b)'s 20/40/60/80% (LG:78).
S2_GARAGE_SHARES = (0.01, 0.12, 0.30, 0.50)   # session 2's Garage shares (before E1), for --previous
MILESTONE_TITLES = {  # D2 placeholders; Board Favorite, Almost Public and Big Bell Boss are the content bible's (BIBLE:174, 224)
    "Garage": ("Side Hustler", "Coffee Powered", "Garage Hero", "Ready to Raise"),
    "Seed": ("Pitch Practicer", "Demo Day Pro", "Growth Hacker", "Series A Bound"),
    "Series A": ("Team Builder", "Product Shipper", "Market Maker", "Series B Bound"),
    "Series B": ("Scale-up Boss", "Campus Planner", "Unicorn Tamer", "Big League Ready"),
    "Series C+D": ("Global Thinker", "Board Favorite", "Tower Builder", "Pre-IPO Bound"),
    "Pre-IPO": ("Roadshow Regular", "Almost Public", "Big Bell Boss", "Ready for the Bell"),
}
D9_WORDS = ("luck", "lucky", "chance", "odds", "jackpot", "prize", "win", "winner", "bet", "gamble", "spin", "roll",
            "lottery", "fortune", "random", "mystery", "reward")   # never in a title (D9)

HEADHUNTER = {"discount": 0.20, "negotiation": (4, 5), "refund": 0.5}   # D5 candidates (placeholders)
EXAMPLES = ("Coding Cat", "Bug Beetle", "Sales Shark", "Server Sloth")    # D5 arithmetic on these


def sig2(x):
    """Round to 2 significant digits (how LONG_ITEMS prices are written)."""
    if x <= 0:
        return 0
    p = 10 ** (int(math.floor(math.log10(x))) - 1)
    return int(round(x / p) * p)


def money(x):
    x = float(x)
    for unit, name in ((1e9, "B"), (1e6, "M"), (1e5, "K")):
        if x >= unit:
            div = 1e3 if name == "K" else unit
            v = x / div
            return "$" + (f"{v:.2f}".rstrip("0").rstrip(".") if v < 10 else f"{v:.1f}".rstrip("0").rstrip(".") if v < 100 else f"{v:.0f}") + name
    return f"${x:,.0f}"


def clock(t):
    if t is None:
        return "none"
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


# ---------------------------------------------------------------------------------------------------------------
# Engine 1: the launch ladder (a fixed buying order). With the previous session's inputs it reproduces model G.
# ---------------------------------------------------------------------------------------------------------------
def ladder_run(ladder, free_hire, milestones, gift=True, stop_val=None, minutes=60, int_pay=False):
    rng = random.Random(SEED)
    queue = [list(row) for row in ladder]
    t, cash, inc, val, chain = 0, 0.0, 0.0, 0.0, 0
    ev, trace, nextcall, hires, eggs, aff, gift_at, ms_done = [], [], None, 0, [], None, None, 0
    calls = []                                   # times of answered calls; chain length after each
    while t <= minutes * 60:
        if t == T_DESK:
            inc += 1
            ev.append((t, "desk", "Desk (free)"))
            nextcall = t + rng.uniform(*CALL["every"])
        if t == T_READY - 2 + GARAGE_EGG["hatch"] + NOTICE:
            inc += free_hire
            hires += 1
            ev.append((t, "hire", "free egg hatched: hire 1"))
        for at, i in list(eggs):
            if t >= at + NOTICE:
                eggs.remove((at, i))
                inc += i
                hires += 1
                ev.append((t, "hire", f"egg hatched: hire {hires}"))
                if hires == 3 and gift:
                    gift_at = t + GIFT_DELAY
        if gift_at is not None and t == gift_at:
            amount = max(DAY1["min"], DAY1["seconds"] * inc)
            cash += amount
            ev.append((t, "gift", f"Day 1 gift +{money(amount)}"))
        if t >= T_DESK and queue:
            name, price, kind, i = queue[0]
            if cash >= price:
                aff = aff if aff is not None else t
                if t - aff >= REACT:
                    cash -= price
                    queue.pop(0)
                    aff = None
                    ev.append((t, "buy", f"{name} {money(price)}"))
                    if kind == "up":
                        inc += i
                    elif kind == "egg":
                        eggs.append((t + GARAGE_EGG["hatch"], GARAGE_EGG_EV if i is None else i))
            else:
                aff = None
        if nextcall is not None and t >= nextcall:
            nextcall = t + rng.uniform(*CALL["every"]) / min(CALL["cap"], 1 + CALL["demand"] * hires)
            if rng.random() < ANSWER_RATE:
                pay = CALL["seconds"] * min(CALL["max"], 1 + CALL["step"] * chain) * inc
                pay = int(pay) if int_pay else pay
                cash += pay
                val += pay
                chain += 1
                calls.append((t, chain, pay))
            else:
                chain = 0
        if t >= T_READY:
            cash += inc
            val += inc
        while ms_done < len(milestones) and val >= milestones[ms_done]:
            ms_done += 1
            ev.append((t, "milestone", f"milestone {ms_done}"))
        trace.append((cash, inc, val, hires, len(ladder) - len(queue), ms_done, len(calls)))
        if stop_val is not None and val >= stop_val:
            ev.append((t, "stage", "Seed"))
            break
        t += 1
    return ev, trace, calls


# ---------------------------------------------------------------------------------------------------------------
# Engine 2: the previous session's greedy model (an egg is bought when it pays back faster than the next upgrade).
# Only for the "today" and "launch as planned" columns; ported line by line so they reproduce.
# ---------------------------------------------------------------------------------------------------------------
def greedy_run(upgrades, egg_price, egg_income, stages, calls, desk2=None, minutes=15, max_hires=5):
    rng = random.Random(SEED)
    t, cash, owned, inc_up, hires, incubators = 0, 0.0, 0, 0.0, [], [T_READY - 2 + GARAGE_EGG["hatch"]]
    val, ev, nextcall, chain, aff, egg_aff, stage_i, answered = 0.0, [], None, 0, None, None, 0, []
    desks = 1 if desk2 else max_hires
    snaps = {}
    while t <= minutes * 60:
        income = inc_up + sum(hires)
        if t % 60 == 0:
            snaps[t // 60] = (cash, income)       # the start of each minute, as the previous model printed it
        if owned == 0 and t >= T_DESK:
            owned = 1
            inc_up += upgrades[0][2]
            ev.append((t, "desk", "Desk (free)"))
            if calls:
                nextcall = t + rng.uniform(*CALL["every"])
        for at in list(incubators):
            if t >= at + NOTICE and len(hires) < min(max_hires, desks):
                incubators.remove(at)
                hires.append(egg_income)
                ev.append((t, "hire", f"hire {len(hires)}"))
        if 0 < owned < len(upgrades):
            name, cost, gain = upgrades[owned]
            if cash >= cost:
                aff = aff if aff is not None else t
                if t - aff >= REACT:
                    cash -= cost
                    owned += 1
                    inc_up += gain
                    ev.append((t, "buy", f"{name} {money(cost)}"))
                    aff = None
            else:
                aff = None
        if desk2 and desks == 1 and len(hires) >= 1 and owned >= 2 and cash >= desk2:
            cash -= desk2
            desks = 2
            ev.append((t, "buy", f"Desk 2 {money(desk2)}"))
        if owned >= 2 and len(incubators) < 3 and len(hires) + len(incubators) < min(max_hires, desks):
            nxt = upgrades[owned] if owned < len(upgrades) else None
            if egg_price / egg_income < (nxt[1] / nxt[2] if nxt else 1e9) and cash >= egg_price:
                egg_aff = egg_aff if egg_aff is not None else t
                if t - egg_aff >= REACT:
                    cash -= egg_price
                    incubators.append(t + GARAGE_EGG["hatch"])
                    ev.append((t, "buy", f"egg {money(egg_price)}"))
                    egg_aff = None
        if calls and nextcall is not None and t >= nextcall:
            nextcall = t + rng.uniform(*CALL["every"]) / min(CALL["cap"], 1 + CALL["demand"] * len(hires))
            if rng.random() < ANSWER_RATE:
                pay = int(CALL["seconds"] * min(CALL["max"], 1 + CALL["step"] * chain) * income + 1e-6)
                cash += pay
                val += pay
                chain += 1
                answered.append((t, chain, pay))
            else:
                chain = 0
        if t >= T_READY:
            cash += income
            val += income
        while stage_i < len(stages) and val >= stages[stage_i][1]:
            ev.append((t, "stage", stages[stage_i][0]))
            stage_i += 1
        t += 1
    return ev, answered, snaps


# ---------------------------------------------------------------------------------------------------------------
# Scenarios and measures
# ---------------------------------------------------------------------------------------------------------------
def pacing(ev, calls):
    def nth(kind, n=1, after=-1):
        hits = [t for t, k, _ in ev if k == kind and t > after]
        return hits[n - 1] if len(hits) >= n else None
    desk = nth("desk")
    marks = [0] + [t for t, k, _ in ev if k in ("desk", "buy", "hire", "stage", "milestone") and t <= 20 * 60]
    mile = [t for t, k, _ in ev if k in ("milestone", "stage")]
    seed = next((t for t, k, n in ev if k == "stage" and n == "Seed"), None)
    late = [t for t, k, _ in ev if k in ("buy", "hire", "stage", "milestone")]
    late = [max([t for t in late if t <= 20 * 60] or [0])] + [t for t in late if t > 20 * 60]
    return {"late": max(b - a for a, b in zip(late, late[1:])) if seed and seed > 20 * 60 else None,
            "desk": desk, "call": calls[0][0] if calls else None, "hire": nth("hire"), "second": nth("buy", after=desk),
            "wait": max(b - a for a, b in zip(marks, marks[1:])), "mile": mile[0] if mile else None,
            "third": nth("hire", 3), "seed": next((t for t, k, n in ev if k == "stage" and n == "Seed"), None)}


def garage_items(scale):
    """Session 2's Garage: D1's ladder with the Whiteboard and Neon Logo scaled (kept for --previous and "unfitted")."""
    rows = [list(r) for r in D1_LADDER]
    for r in rows:
        if r[0] in D1_FIT:
            r[1] = sig2(r[1] * scale)
    return rows


def e1_items(prices):
    """D1's ladder with the Whiteboard and Neon Logo split into levels I and II (E1); `prices` may be a prefix."""
    return [list(r) for r in D1_LADDER if r[0] not in D1_FIT] + [[n, p, "up", i] for (n, _, i), p in zip(E1_LEVELS, prices)]


def thresholds(garage_sum):
    """Valuation to enter each next rung: LONG_K x the price of everything so far, with D1's Garage."""
    sums = [garage_sum] + LONG_RUNG_SUMS[1:]
    return [LONG_K * sum(sums[: r + 1]) for r in range(len(sums))]


def milestones_for(rung, entry, nxt, shares=None):
    shares = shares or MILESTONE_SHARES["Garage" if rung == 0 else "other"]
    return [sig2(entry + s * (nxt - entry)) for s in shares]


def garage_run(rows, shares, minutes=4 * 60):
    seed = thresholds(sum(r[1] for r in rows))[0]
    ev, trace, calls = ladder_run(rows, GARAGE_EGG_EV, milestones_for(0, 0, seed, shares), stop_val=seed, minutes=minutes)
    return dict(ev=ev, trace=trace, calls=calls, rows=rows, seed=seed)


def d1_run(scale, minutes=4 * 60):
    return dict(garage_run(garage_items(scale), S2_GARAGE_SHARES, minutes), scale=scale)


def fit_scale():
    """Session 2's fit: the smallest factor (steps of 0.1) that puts Seed at 1:30:00 or later."""
    for k in range(10, 101):
        run = d1_run(k / 10)
        seed_t = pacing(run["ev"], run["calls"])["seed"]
        if seed_t is not None and seed_t >= GARAGE_TARGET:
            return run
    raise SystemExit("no factor up to 10 reaches the Garage target")


def late_gaps(ev):
    """Every wait from the last event before 20:00 to Seed, largest first (assumption 13's events)."""
    ts = [t for t, k, _ in ev if k in ("buy", "hire", "stage", "milestone")]
    late = [max([t for t in ts if t <= 20 * 60] or [0])] + [t for t in ts if t > 20 * 60]
    return sorted((b - a for a, b in zip(late, late[1:])), reverse=True)


def fit_score(prices, shares):
    run = garage_run(e1_items(prices), shares, minutes=3 * 60)
    pc = pacing(run["ev"], run["calls"])
    if pc["seed"] is None or pc["mile"] is None:
        return (1e9,)
    return (max(0, GARAGE_TARGET - pc["seed"]) + max(0, pc["seed"] - GARAGE_TARGET - 60), max(0, pc["mile"] - 600),
            max(0, pc["wait"] - 390), tuple(late_gaps(run["ev"])))


def fit():
    """--fit (assumption 12). 1) Levels on evenly spaced slots after the Server Rack (E1_SLOTS): each price is the
    highest 2-digit price still bought by its slot; the spacing is the shortest that puts Seed at 1:30:00 or later.
    2) Milestones 2-4 at the valuation halfway (in time) through the waits after the Whiteboard II, the
    Neon Logo I and the Neon Logo II. 3) Steps of
    1 or 3 in a price's second digit and 1 or 2 points in a share, kept while fit_score improves. Deterministic."""
    grid = sorted({sig2(v) for v in range(10000, 1000000, 100)})
    rack = next(t for t, k, n in ladder_run(e1_items([]), GARAGE_EGG_EV, [])[0] if n.startswith("Server Rack"))
    buys = [i + 1 for i, c in enumerate(E1_SLOTS) if c == "B"]

    def bought(prices):
        name = E1_LEVELS[len(prices) - 1][0] + " $"
        return next((t for t, k, n in ladder_run(e1_items(prices), GARAGE_EGG_EV, [], minutes=3 * 60)[0] if n.startswith(name)), None)

    for gap in range(8 * 60, 13 * 60, 5):
        prices = []
        for slot in buys:
            lo, hi = grid.index(prices[-1]) if prices else 0, len(grid) - 1
            while lo < hi:                                # the highest price bought by the slot
                mid = (lo + hi + 1) // 2
                t = bought(prices + [grid[mid]])
                lo, hi = (mid, hi) if t is not None and t <= rack + slot * gap else (lo, mid - 1)
            prices.append(grid[lo])
        run = garage_run(e1_items(prices), S2_GARAGE_SHARES, minutes=3 * 60)
        if pacing(run["ev"], run["calls"])["seed"] >= GARAGE_TARGET:
            break

    def midpoints(prices):
        run = garage_run(e1_items(prices), S2_GARAGE_SHARES, minutes=3 * 60)
        at_ = [next(t for t, k, n in run["ev"] if n.startswith(name + " $")) for name, _, _ in E1_LEVELS]
        ends = at_[1:] + [next(t for t, k, n in run["ev"] if k == "stage")]
        return (MILESTONE_SHARES["Garage"][0],) + tuple(round(run["trace"][(a + b) // 2][2] / run["seed"], 2)
                                                        for a, b in zip(ends, ends[1:]))

    shares = midpoints(prices)
    best = fit_score(prices, shares)
    better = True
    while better:
        better = False
        for i in range(len(prices)):
            unit = 10 ** (int(math.floor(math.log10(prices[i]))) - 1)
            for d in (-3, -1, 1, 3):
                cand = prices[:i] + [sig2(prices[i] + d * unit)] + prices[i + 1:]
                if cand != sorted(cand):
                    continue
                for sh in (shares, midpoints(cand)):
                    sc = fit_score(cand, sh)
                    if sc < best:
                        best, prices, shares, better = sc, cand, sh, True
        for i in range(1, len(shares)):
            for d in (-0.02, -0.01, 0.01, 0.02):
                sh = shares[:i] + (round(shares[i] + d, 2),) + shares[i + 1:]
                if list(sh) == sorted(sh) and sh[-1] < 1:
                    sc = fit_score(prices, sh)
                    if sc < best:
                        best, shares, better = sc, sh, True
    return prices, shares, gap


def scenarios():
    today = greedy_run(TODAY_UPGRADES, GARAGE_EGG["price"], GARAGE_EGG_EV, TODAY_STAGES, calls=False)
    studio = greedy_run(TODAY_UPGRADES, GARAGE_EGG["price"], GARAGE_EGG_EV, TODAY_STAGES, calls=True)
    p = LONG_GARAGE_PLANNED
    planned_up = [("Desk", 0, 1), ("Coffee Machine", p["Coffee Machine"], 2), ("Laptop", p["Laptop"], 5),
                  ("Server Rack", 13000, 15), ("Whiteboard", 28000, 40), ("Neon Logo", 72000, 120)]
    planned = greedy_run(planned_up, p["egg"], 3.0, [("Seed", LONG_K * LONG_RUNG_SUMS[0])], calls=True,
                         desk2=p["Desk 2"], minutes=30)
    d1 = garage_run(e1_items([p for _, p, _ in E1_LEVELS]), MILESTONE_SHARES["Garage"])
    return dict(today=today[:2], today_snaps=today[2], studio=studio, planned=planned[:2], unfit=d1_run(1.0), d1=d1)


# ---------------------------------------------------------------------------------------------------------------
# Tables. Each is one block in the doc; its first line (the header row) is its id.
# ---------------------------------------------------------------------------------------------------------------
def at(run, t):
    cash, inc, val, hires, bought, ms, answered = run["trace"][t]
    return cash, inc, val, hires, bought, ms, answered


def table_today(s):
    ev, snaps = s["today"][0], s["today_snaps"]
    when = lambda evs, pred: clock(next(t for t, k, n in evs if pred(k, n)))
    cash = ", ".join(f"{m}:00 ${int(snaps[m][0]):,} / ${snaps[m][1]:.0f}" for m in (1, 2, 4, 5, 10))   # truncated, as before
    st = s["studio"][0]
    return [f"Today, live (model): Cash / Income at {cash}; Neon Logo {when(ev, lambda k, n: n.startswith('Neon'))}, "
            f"five hires {when(ev, lambda k, n: n == 'hire 5')}, IPO-ready {when(ev, lambda k, n: n == 'IPO-ready')}. "
            f"With Studio calls: first call {clock(s['studio'][1][0][0])}, Seed {when(st, lambda k, n: n == 'Seed')}, "
            f"Garage done {when(st, lambda k, n: n.startswith('Neon'))}, IPO-ready {when(st, lambda k, n: n == 'IPO-ready')}."]


def table_pacing(s):
    a, d = pacing(*s["today"]), pacing(*s["planned"])
    g, u = pacing(s["d1"]["ev"], s["d1"]["calls"]), pacing(s["unfit"]["ev"], s["unfit"]["calls"])
    rows = [("Desk", "≤ 0:30", clock(a["desk"]), clock(d["desk"]), clock(g["desk"])),
            ("First call", "≤ 1:00", "none live", clock(d["call"]), clock(g["call"])),
            ("First hire", "≤ 1:30", clock(a["hire"]), clock(d["hire"]), clock(g["hire"])),
            ("Second purchase", "≤ 2:00", clock(a["second"]), clock(d["second"]), clock(g["second"])),
            ("Longest wait, 0-20 min", "≤ 6:30", clock(a["wait"]), clock(d["wait"]), clock(g["wait"])),
            ("Longest wait, 20 min to Seed", "≤ 15:00", "Seed before 20 min", "not modelled", clock(g["late"])),
            ("First milestone (today: stage)", "≤ 10:00", clock(a["mile"]) + " Seed", "none before Seed", clock(g["mile"])),
            ("Third hire", "≤ 15:00", clock(a["third"]), "none in 30 min" if d["third"] is None else clock(d["third"]), clock(g["third"])),
            ("Seed", "about 1:30:00", clock(a["seed"]), "1:30:00 (LONG's fit)", f"{clock(g['seed'])} ({clock(u['seed'])} unfitted)")]
    out = ["| Moment (model) | Target | Today | Launch as planned | Launch with D1, E1 |", "|---|---|---|---|---|"]
    return out + ["| " + " | ".join(r) + " |" for r in rows]


BEATS = [  # what the tutorial, the goal card or the world adds at an event (design, not model output)
    ("Desk (free)", "TUT 1; Cash on the bar"), ("first call", "TUT 5; goal: 3 calls"), ("free egg", "TUT 2; goal: 3 hires"),
    ("Coffee", "TUT 4: own Cash"), ("third call", "goal done"), ("Laptop", "goal: 3 upgrades done"),
    ("Desk 2", "TUT 3: one hire per desk"), ("hire 2", "hires 2/3"), ("10th call", "decor: Beanbag Throne"),
    ("milestone 1", "a star, title Side Hustler"),
]


def table_script(s):
    run = s["d1"]
    rows = [(t, n) for t, k, n in run["ev"] if t <= 10 * 60 and k != "gift"]
    rows.append((run["calls"][0][0], f"first call answered +{money(run['calls'][0][2])}"))
    rows.append((run["calls"][2][0], "third call answered"))
    rows.append((run["calls"][9][0], "10th call answered"))
    rows.sort()
    out = ["| Time | Event (D1, E1 run) | Tutorial, goal, reward | Cash / Income |", "|---|---|---|---|"]
    for t, name in rows:
        cash, inc, *_ = at(run, t)
        beat = next((b for key, b in BEATS if key in name), "")
        out.append(f"| {clock(t)} | {name} | {beat} | {money(cash)} / ${inc:.0f} |")
    cash, inc, val, hires, bought, ms, answered = at(run, 600)
    out.append(f"| 10:00 | {answered} calls, {hires} hires, {bought} of {len(run['rows'])} items | next: Server Rack | {money(cash)} / ${inc:.0f} |")
    return out


def table_hour(s):
    run = s["d1"]
    ev, calls = run["ev"], run["calls"]
    find = lambda pred: next((t for t, k, n in ev if pred(k, n)), None)
    goals = [("Answer 3 calls", calls[2][0]),
             ("Own 3 upgrades", find(lambda k, n: n.startswith("Laptop"))),
             ("Reach milestone 1", find(lambda k, n: n == "milestone 1")),
             ("Hire 3 employees", [t for t, k, n in ev if k == "hire"][2]),
             ("Get a x2 chain", next((t for t, c, p in calls if c >= 11), None)),
             ("Buy the Server Rack", find(lambda k, n: n.startswith("Server Rack"))),
             ("Reach milestone 2", find(lambda k, n: n == "milestone 2")),
             ("Reach milestone 3", find(lambda k, n: n == "milestone 3")),
             ("Reach milestone 4", find(lambda k, n: n == "milestone 4")),
             ("Reach Seed", find(lambda k, n: k == "stage")),
             ("(not a goal) TUT 6: " + next(n for t, k, n in ev if k == "gift"), find(lambda k, n: k == "gift"))]
    out = ["| Goal (D1, E1 run) | Done at |", "|---|---|"]
    out += [f"| {g} | {clock(t) if t is not None else 'not in 4 h'} |" for g, t in goals]
    out += ["", "| At (D1, E1 run) | Items bought | Hires | Calls answered | Milestones | Cash / Income | Seed bar |", "|---|---|---|---|---|---|---|"]
    for m in (5, 20, 60):
        cash, inc, val, hires, bought, ms, answered = at(run, m * 60)
        out.append(f"| {m} min | {bought} of {len(run['rows'])} | {hires} | {answered} | {ms} | {money(cash)} / ${inc:.0f} | {val / run['seed']:.0%} |")
    return out


def table_garage(s):
    run = s["d1"]
    p = LONG_GARAGE_PLANNED
    plan = {"Coffee Machine": p["Coffee Machine"], "Laptop": p["Laptop"], "Desk 2": p["Desk 2"], "Garage Egg": p["egg"],
            "Server Rack": 13000, "Whiteboard I": 28000, "Neon Logo I": 72000}
    out = ["| Garage item (D1, E1) | LONG plan | Placeholder | Income | Bought at |", "|---|---|---|---|---|"]
    seen = set()
    for name, price, kind, inc in run["rows"]:
        if name in seen:
            continue                                  # the two Garage Eggs share one row
        seen.add(name)
        times = [t for t, k, n in run["ev"] if k == "buy" and n == f"{name} {money(price)}"]
        cost = money(plan[name]) + (" (one level)" if name.endswith(" I") else "") if name in plan else "in level I" if name.endswith(" II") else "none"
        gain = {"up": f"+${inc}/s", "desk": "a desk", "egg": "a hire"}[kind]
        out.append(f"| {name} | {cost} | {money(price)} | {gain} | {', '.join(clock(t) for t in times)} |")
    seed_t = next(t for t, k, n in run["ev"] if k == "stage")
    out.append(f"| Enter Seed at | {money(LONG_K * LONG_RUNG_SUMS[0])} | {money(run['seed'])} | | {clock(seed_t)} |")
    return out


def table_milestones(s):
    run = s["d1"]
    th = thresholds(sum(r[1] for r in run["rows"]))
    out = ["| Rung (LONG, D1 Garage) | Enters at | Milestones 1-4 (valuation) | Titles 1-4 | Next rung at |", "|---|---|---|---|---|"]
    for r, name in enumerate(LONG_RUNGS):
        entry = 0 if r == 0 else th[r - 1]
        ms = milestones_for(r, entry, th[r])
        out.append(f"| {name} | {money(entry)} | {', '.join(money(m) for m in ms)} | {', '.join(MILESTONE_TITLES[name])} | {money(th[r])} |")
    stages = [("Garage", 0)] + TODAY_STAGES
    today = [f"{stages[i][0]} {', '.join(money(m) for m in milestones_for(i, stages[i][1], stages[i + 1][1]))}"
             for i in range(len(stages) - 1)]
    out += ["", "With today's IpoConfig stages instead: " + "; ".join(today) + "."]
    return out


def poach_price(creature):
    name, income, rarity, tier = creature
    egg, ref_name, ref_inc = next((p, n, i) for t, p, n, i in LONG_EGG_TIERS if t == tier)
    return sig2(max(egg, income * egg / ref_inc))


def table_poach():
    out = ["| Home egg tier (egg at launch) | Seconds of Income | Reference and priciest hire: today → launch | Cash per success at base chance |",
           "|---|---|---|---|"]
    for tier, egg, ref, ref_inc in LONG_EGG_TIERS:
        group = [h for h in HIRES if h[3] == tier]
        ends = [next((h for h in group if h[0] == ref), group[0]), group[-1]]   # the hire the egg is priced at, the priciest
        cells = [f"{c[0]} {money(max(POACH_TODAY['min'], c[1] * POACH_TODAY['seconds']))} → {money(poach_price(c))}" for c in ends]
        per = [f"{money(poach_price(c) / BASE_CHANCE[c[2]])}" if c[2] in BASE_CHANCE else
               "never (Legendary)" if c[2] == "Legendary" else "rarity not set" for c in ends]
        per = per[0] if per[0] == per[1] else f"{per[0]}; {per[1]}"
        out.append(f"| {tier} ({money(egg)}) | {egg / ref_inc:,.0f} | {'; '.join(cells)} | {per} |")
    return out


def table_headhunter():
    ex = [h for h in HIRES if h[0] in EXAMPLES]
    head = " | ".join(f"{c[0]} {money(poach_price(c))}, {BASE_CHANCE[c[2]]:.0%}" for c in ex)
    out = [f"| Headhunter effect | {head} | Attempts per hour |", "|---" * (len(ex) + 2) + "|"]
    cycle = sum(NEGOTIATION) / 2 + ATTACKER_COOLDOWN
    short = sum(HEADHUNTER["negotiation"]) / 2 + ATTACKER_COOLDOWN
    d, r = HEADHUNTER["discount"], HEADHUNTER["refund"]
    rows = [("No pass", lambda P, p: P / p, cycle),
            (f"Today: +{HEADHUNTER_TODAY:.0%} chance (the victim's risk too)", lambda P, p: P / (p + HEADHUNTER_TODAY), cycle),
            (f"A. {d:.0%} off every poach", lambda P, p: (1 - d) * P / p, cycle),
            (f"B. Negotiation {HEADHUNTER['negotiation'][0]}-{HEADHUNTER['negotiation'][1]} s", lambda P, p: P / p, short),
            (f"C. {r:.0%} back when a poach fails", lambda P, p: P * (p + r * (1 - p)) / p, cycle)]
    for label, cost, cyc in rows:
        cells = []
        for c in ex:
            P, p = poach_price(c), BASE_CHANCE[c[2]]
            base = P / p
            v = cost(P, p)
            cells.append(f"{money(v)}" + ("" if abs(v - base) < 0.5 else f" ({v / base - 1:+.0%})"))
        out.append(f"| {label} | {' | '.join(cells)} | {3600 / cyc:.0f} |")
    return out


TABLES = [table_today, table_pacing, table_script, table_hour, table_garage, table_milestones, lambda s: table_poach(), lambda s: table_headhunter()]


def all_tables():
    s = scenarios()
    return [t(s) for t in TABLES]


def previous_g():
    """The previous session's model G (scratch file g3_model.py): free egg and bought eggs at fixed Incomes (3, 3, 8),
    no Day 1 gift, Income floored on call pay, milestones at $5K / $20K / $60K / $120K, 40 minutes."""
    ladder = [list(r) for r in D1_LADDER[:-1]]
    ladder[3][3], ladder[5][3] = 3, 8
    ev, trace, calls = ladder_run(ladder, 3, [5000, 20000, 60000, 120000], gift=False, minutes=40, int_pay=True)
    return [f"{clock(t)} {n}" for t, k, n in ev]


PREVIOUS = {  # what sessions 1 and 2 printed (docs/GAMEPLAY_NOTES.md, "The model"); --previous fails if one drifts
    "A, B (today, live and with Studio calls)": "Today, live (model): Cash / Income at 1:00 $29 / $1, 2:00 $398 / $13, 4:00 $3,989 / $68, "
        "5:00 $6,997 / $188, 10:00 $67,672 / $208; Neon Logo 4:20, five hires 7:10, IPO-ready 10:25. With Studio calls: "
        "first call 0:53, Seed 2:30, Garage done 3:48, IPO-ready 8:40.",
    "D (launch as planned)": "first call 0:53; 0:30 Desk (free), 1:22 hire 1, 5:01 Coffee Machine $1,100, 13:20 Desk 2 $3,600, "
        "18:11 egg $2,300, 19:31 hire 2, 25:04 Laptop $4,200; longest wait 8:19",
    "G (session 1's D1)": "0:30 Desk (free), 1:22 free egg hatched: hire 1, 1:43 Coffee Machine $150, 3:34 Laptop $800, 4:51 Desk 2 $1,000, "
        "5:21 Garage Egg $400, 6:41 egg hatched: hire 2, 8:02 milestone 1, 10:25 Desk 3 $5,000, 10:54 Garage Egg $400, "
        "12:14 egg hatched: hire 3, 18:27 milestone 2, 19:00 Server Rack $13,000, 28:37 Whiteboard $28,000, 30:05 milestone 3, "
        "39:13 milestone 4",
    "session 2's D1 (before E1)": "x3.1: Whiteboard $87,000 at 41:02, Neon Logo $220K at 1:18:59, Seed $492K at 1:30:04 (37:02 unfitted); "
        "longest wait 0-20 min 2:52, 20 min to Seed 17:11; milestones 6:47, 27:55, 49:43, 1:06:54",
}


def previous():
    s = scenarios()
    ev, calls = s["planned"]
    d, g = pacing(ev, calls), fit_scale()
    pg, u = pacing(g["ev"], g["calls"]), pacing(s["unfit"]["ev"], s["unfit"]["calls"])
    find = lambda name: clock(next(t for t, k, n in g["ev"] if n.startswith(name)))
    got = {
        "A, B (today, live and with Studio calls)": table_today(s)[0],
        "D (launch as planned)": f"first call {clock(d['call'])}; " + ", ".join(f"{clock(t)} {n}" for t, k, n in ev) + f"; longest wait {clock(d['wait'])}",
        "G (session 1's D1)": ", ".join(previous_g()),
        "session 2's D1 (before E1)": f"x{g['scale']:.1f}: Whiteboard {money(g['rows'][7][1])} at {find('Whiteboard')}, Neon Logo "
            f"{money(g['rows'][8][1])} at {find('Neon Logo')}, Seed {money(g['seed'])} at {clock(pg['seed'])} ({clock(u['seed'])} unfitted); "
            f"longest wait 0-20 min {clock(pg['wait'])}, 20 min to Seed {clock(pg['late'])}; milestones "
            + ", ".join(clock(t) for t, k, n in g["ev"] if k == "milestone"),
    }
    bad = 0
    for name, want in PREVIOUS.items():
        ok = got[name] == want
        bad += not ok
        print(f"{name}: {'reproduced' if ok else 'DIFFERS'}\n  {got[name]}" + ("" if ok else f"\n  was: {want}"))
    return 1 if bad else 0


# ---------------------------------------------------------------------------------------------------------------
# --check: the doc's blocks against this output, and the copied constants against their sources
# ---------------------------------------------------------------------------------------------------------------
def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def source_errors():
    errs = []

    def want(ok, what):
        if not ok:
            errs.append(f"source drift: {what}")

    tc = read("TycoonCore.lua")
    for name, cost, inc in TODAY_UPGRADES:
        want(re.search(r'name = "%s",\s+cost = %d,\s+income = %d,' % (re.escape(name), cost, inc), tc), f"TycoonCore UPGRADES {name}")
    cc = read("CreatureConfig.lua")
    want(re.search(r'key = "Garage",\s+name = "Garage Egg",\s+price = %d,\s+hatchSeconds = %d,' % (GARAGE_EGG["price"], GARAGE_EGG["hatch"]), cc), "Garage Egg price/hatch")
    want("odds = { Common = 70, Uncommon = 25, Rare = 5 }" in cc, "Garage Egg odds")
    want(f"CostIncomeSeconds = {POACH_TODAY['seconds']}," in cc and f"MinCost = {POACH_TODAY['min']}," in cc, "poach cost rule")
    want("BaseChance = { Common = 0.6, Uncommon = 0.5, Rare = 0.4, Epic = 0.3, Legendary = false }" in cc, "poach BaseChance")
    want(f"NegotiationSeconds = {{ {NEGOTIATION[0]}, {NEGOTIATION[1]} }}" in cc and f"AttackerCooldown = {ATTACKER_COOLDOWN}," in cc, "negotiation/cooldown")
    for rarity, incs in GARAGE_INCOMES.items():
        found = sorted(int(m) for m in re.findall(r'rarity = "%s",[^\n]*?income = (\d+)' % rarity, cc))
        want(found == sorted(incs), f"{rarity} Incomes {found}")
    ipo = read("IpoConfig.lua")
    for name, v in TODAY_STAGES:
        want(re.search(r'name = "%s", icon = "[^"]+", valuation = %d' % (re.escape(name), v), ipo), f"IpoConfig stage {name}")
    task = read("TaskConfig.lua")
    want("every = { 20, 40 }" in task and "reward = { seconds = 7, chain = { step = 0.1, max = 2 } }" in task
         and "demand = 0.08" in task and "TaskConfig.DemandCap = 2.0" in task, "TaskConfig Call row")
    daily = read("DailyConfig.lua")
    want('{ key = "Day1", cashMinutes = 5,' in daily and "DailyConfig.MinCash = 300" in daily, "DailyConfig Day 1")
    want("effect = { poachBonus = 0.1 }" in read("ShopConfig.lua"), "Headhunter poachBonus")
    sim = read("tools/economy_sim.py")
    want(re.search(r"^LONG_K = 1\.5\b", sim, re.M), "LONG_K")
    block = sim[sim.index("LONG_ITEMS = ["): sim.index("]\n", sim.index("LONG_ITEMS = ["))]
    items = [(int(r), n, int(p)) for r, k, n, p in re.findall(r'\((\d), "(\w+)", "([^"]+)", (\d+), [\d.]+\)', block)]
    sums = [sum(p for r, n, p in items if r == i) for i in range(len(LONG_RUNGS))]
    want(sums == LONG_RUNG_SUMS, f"LONG_ITEMS rung sums {sums}")
    g = {n: p for r, n, p in items if r == 0}
    want(g.get("Coffee Machine") == LONG_GARAGE_PLANNED["Coffee Machine"] and g.get("Laptop") == LONG_GARAGE_PLANNED["Laptop"]
         and g.get("Desk 2") == LONG_GARAGE_PLANNED["Desk 2"] and g.get("Coding Cat") == LONG_GARAGE_PLANNED["egg"], "LONG Garage prices")
    for name, titles in MILESTONE_TITLES.items():
        for title in titles:
            bad = [w for w in D9_WORDS if re.search(r"\b%s\b" % w, title.lower())]
            want(not bad, f"title {title!r} uses {bad} (D9)")
    return errs


def check():
    text = DOC.read_text(encoding="utf-8")
    blocks = re.findall(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), text, re.S)
    tables = {t[0]: t for t in all_tables()}
    errs, seen = source_errors(), set()
    for b in blocks:
        lines = [ln.rstrip() for ln in b.strip().splitlines()]
        want = tables.get(lines[0])
        if want is None:
            errs.append(f"doc block with an unknown first line: {lines[0][:80]}")
            continue
        seen.add(lines[0])
        for i, (got, exp) in enumerate(zip(lines, want)):
            if got != exp:
                errs.append(f"block '{lines[0][:40]}...' line {i + 1}:\n  doc:   {got}\n  model: {exp}")
                break
        if len(lines) != len(want):
            errs.append(f"block '{lines[0][:40]}...': {len(lines)} lines in the doc, {len(want)} in the model")
    for head in tables:
        if head not in seen:
            errs.append(f"model table missing from the doc: {head[:80]}")
    for e in errs:
        print(e)
    print(f"--check: {len(blocks)} blocks, {len(errs)} problem(s)")
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="compare the doc's blocks and the copied constants")
    ap.add_argument("--previous", action="store_true", help="reproduce sessions 1-2's models A, B, D, G and session 2's Garage")
    ap.add_argument("--fit", action="store_true", help="re-run the E1 Garage fit and compare it with E1_LEVELS")
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    if args.previous:
        sys.exit(previous())
    if args.fit:
        prices, shares, gap = fit()
        sc = fit_score(prices, shares)
        same = prices == [p for _, p, _ in E1_LEVELS] and shares == MILESTONE_SHARES["Garage"]
        print(f"fit: levels {', '.join(money(p) for p in prices)}; Garage milestone shares {', '.join(f'{x:.0%}' for x in shares)}; "
              f"start spacing {clock(gap)}; waits after 20:00 {', '.join(clock(x) for x in sc[3])}")
        print("matches E1_LEVELS and MILESTONE_SHARES" if same else "DIFFERS from E1_LEVELS / MILESTONE_SHARES: copy the fit into them")
        sys.exit(0 if same else 1)
    for table in all_tables():
        print(BEGIN)
        print("\n".join(table))
        print(END)
        print()


if __name__ == "__main__":
    main()
