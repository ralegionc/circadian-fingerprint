"""
Reduce GH Archive hourly counts to weekday x hour fingerprints.

The primary measure is *distinct accounts active in the hour*, not events.
Events measure automation: in one sampled hour the ten busiest accounts produced
a quarter of all pushes, and the heaviest of them carried no [bot] suffix, so an
event-weighted curve is dominated by a handful of scripts. Counting accounts
gives every participant equal weight and is what a "how many people were here"
curve actually needs. Event curves are kept alongside for comparison.

GH Archive stamps everything in UTC and carries no location, so there is no
local-time view to build here -- this is the platform's pulse as the platform
experiences it.
"""
import collections
import datetime as dt
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from event_groups import GROUPS, HEAVY_THRESHOLD

RAW = os.path.join(HERE, "..", "data", "raw", "gharchive_hours.jsonl")
OUT = os.path.join(HERE, "..", "data", "processed", "github_fingerprints.json")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TYPE_TO_GROUP = {t: g for g, ts in GROUPS.items() for t in ts}


def blank():
    return [[[] for _ in range(24)] for _ in range(7)]


def means(cells):
    return [[statistics.mean(c) if c else 0.0 for c in row] for row in cells]


def normalise(mat):
    flat = [v for row in mat for v in row]
    avg = sum(flat) / len(flat)
    return [[(v / avg if avg else 0.0) for v in row] for row in mat]


def summarise(norm):
    by_hour = [sum(norm[d][h] for d in range(7)) / 7 for h in range(24)]
    by_day = [sum(norm[d]) / 24 for d in range(7)]
    weekday = sum(by_day[0:5]) / 5
    weekend = sum(by_day[5:7]) / 2
    lo = min(by_hour)
    return {
        "by_hour": [round(v, 4) for v in by_hour],
        "by_day": [round(v, 4) for v in by_day],
        "peak_hour": max(range(24), key=lambda h: by_hour[h]),
        "trough_hour": min(range(24), key=lambda h: by_hour[h]),
        "hour_amplitude": round(max(by_hour) / lo, 2) if lo else None,
        "weekend_ratio": round(weekend / weekday, 3) if weekday else None,
    }


def pack(cells, total=None):
    mat = means(cells)
    norm = normalise(mat)
    out = {
        "matrix": [[round(v, 2) for v in row] for row in mat],
        "norm": [[round(v, 4) for v in row] for row in norm],
        "stats": summarise(norm),
    }
    if total is not None:
        out["total"] = total
    return out


def main():
    recs = {}
    for line in open(RAW, encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "error" not in r:
            recs[(r["date"], r["hour"])] = r
    recs = list(recs.values())
    if not recs:
        print("no records yet")
        return

    actor_cells = collections.defaultdict(blank)   # (group, bot) -> cells
    event_cells = collections.defaultdict(blank)   # (group, bot) -> cells
    heavy_cells, heavy_ev_cells, human_ev_cells = blank(), blank(), blank()
    event_totals = collections.Counter()

    for r in recs:
        wd = dt.date.fromisoformat(r["date"]).weekday()
        hr = r["hour"]
        for key, n in r.get("actors", {}).items():
            group, bot = key.rsplit("|", 1)
            actor_cells[(group, bot == "1")][wd][hr].append(n)
        per = collections.Counter()
        for key, v in r["counts"].items():
            etype, bot = key.rsplit("|", 1)
            group = TYPE_TO_GROUP.get(etype)
            if group:
                per[(group, bot == "1")] += v
                event_totals[(group, bot == "1")] += v
            per[("ALL", bot == "1")] += v
            event_totals[("ALL", bot == "1")] += v
        for key, v in per.items():
            event_cells[key][wd][hr].append(v)
        heavy_cells[wd][hr].append(r.get("heavy_actors", 0))
        heavy_ev_cells[wd][hr].append(r.get("heavy_events", 0))
        human_ev_cells[wd][hr].append(r.get("human_events", 0))

    groups = [g for g in GROUPS]
    payload = {
        "hours_ingested": len(recs),
        "days": DAYS,
        "total_events": sum(r["lines"] for r in recs),
        "heavy_threshold": HEAVY_THRESHOLD,
        "actors": {
            "human": {g: pack(actor_cells[(g, False)])
                      for g in ["ALL"] + groups if (g, False) in actor_cells},
            "bot": {g: pack(actor_cells[(g, True)])
                    for g in ["ALL"] + groups if (g, True) in actor_cells},
        },
        "events": {
            "human": {g: pack(event_cells[(g, False)], event_totals[(g, False)])
                      for g in ["ALL"] + groups if (g, False) in event_cells},
            "bot": {g: pack(event_cells[(g, True)], event_totals[(g, True)])
                    for g in ["ALL"] + groups if (g, True) in event_cells},
        },
        "automation": {
            "heavy_actors": pack(heavy_cells),
            "mean_heavy_actors_per_hour": round(
                statistics.mean(r.get("heavy_actors", 0) for r in recs), 1),
            "heavy_event_share": round(
                sum(r.get("heavy_events", 0) for r in recs)
                / max(1, sum(r.get("human_events", 0) for r in recs)), 4),
            "bot_event_share": round(
                event_totals[("ALL", True)]
                / max(1, event_totals[("ALL", True)] + event_totals[("ALL", False)]), 4),
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w", encoding="utf-8"))

    a = payload["automation"]
    print(f"{len(recs)} hours, {payload['total_events']:,} events -> {OUT}")
    print(f"bots: {a['bot_event_share']*100:.1f}% of events | "
          f"heavy human accounts (>={HEAVY_THRESHOLD}/hr): "
          f"{a['mean_heavy_actors_per_hour']} per hour, "
          f"{a['heavy_event_share']*100:.1f}% of human events\n")

    print(f"{'series':<22}{'measure':>10}{'peak':>7}{'trough':>8}{'amp':>7}{'wknd':>7}")
    print("-" * 61)
    for g in ["ALL"] + groups:
        for label, blob in (("accounts", payload["actors"]["human"].get(g)),
                            ("events", payload["events"]["human"].get(g))):
            if not blob:
                continue
            s = blob["stats"]
            print(f"{(g + ' (human)'):<22}{label:>10}{s['peak_hour']:>5}:00"
                  f"{s['trough_hour']:>6}:00{str(s['hour_amplitude']):>7}"
                  f"{str(s['weekend_ratio']):>7}")
    s = payload["actors"]["bot"]["ALL"]["stats"]
    print(f"{'ALL (bot)':<22}{'accounts':>10}{s['peak_hour']:>5}:00"
          f"{s['trough_hour']:>6}:00{str(s['hour_amplitude']):>7}{str(s['weekend_ratio']):>7}")


if __name__ == "__main__":
    main()
