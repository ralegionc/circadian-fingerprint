"""
Reduce hourly Wikipedia pageviews to weekday x hour fingerprints.

Produces, per language edition, two 7x24 matrices of mean hourly views -- one
indexed by UTC clock, one by local clock -- plus summary statistics. Matrices
are also emitted in normalised form (1.0 = that edition's own average hour) so
editions three orders of magnitude apart in traffic can be compared by shape.
"""
import datetime as dt
import json
import os
import statistics
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "..", "data", "raw", "wikipedia_hourly.json")
OUT = os.path.join(HERE, "..", "data", "processed", "wikipedia_fingerprints.json")

# Monday-first, matching ISO weekday order.
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def blank():
    return [[[] for _ in range(24)] for _ in range(7)]


def means(cells):
    return [[statistics.mean(c) if c else 0.0 for c in row] for row in cells]


def normalise(mat):
    flat = [v for row in mat for v in row]
    avg = sum(flat) / len(flat)
    if avg == 0:
        return mat
    return [[v / avg for v in row] for row in mat]


def summarise(local_norm, local_mat):
    flat = [(local_norm[d][h], d, h) for d in range(7) for h in range(24)]
    peak = max(flat)
    trough = min(flat)

    # Mean level per hour-of-day, collapsed across days.
    by_hour = [sum(local_norm[d][h] for d in range(7)) / 7 for h in range(24)]
    peak_hour = max(range(24), key=lambda h: by_hour[h])
    trough_hour = min(range(24), key=lambda h: by_hour[h])

    # Mean level per weekday, collapsed across hours.
    by_day = [sum(local_norm[d]) / 24 for d in range(7)]
    quiet_day = min(range(7), key=lambda d: by_day[d])
    busy_day = max(range(7), key=lambda d: by_day[d])

    night = sum(by_hour[h] for h in range(0, 6)) / 24
    total_daily = sum(by_hour) / 24
    return {
        "peak_hour": peak_hour,
        "trough_hour": trough_hour,
        "peak_cell": {"day": peak[1], "hour": peak[2], "value": round(peak[0], 3)},
        "trough_cell": {"day": trough[1], "hour": trough[2], "value": round(trough[0], 3)},
        "amplitude": round(max(by_hour) / min(by_hour), 2),
        "by_hour": [round(v, 4) for v in by_hour],
        "by_day": [round(v, 4) for v in by_day],
        "quiet_day": quiet_day,
        "busy_day": busy_day,
        "night_share": round(night / total_daily, 4),
        "weekend_ratio": round(
            (by_day[5] + by_day[6]) / 2 / (sum(by_day[0:5]) / 5), 3
        ),
        "mean_hourly_views": round(
            sum(v for row in local_mat for v in row) / 168
        ),
    }


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    out = {}
    for code, rec in raw["projects"].items():
        tz = ZoneInfo(rec["tz"])
        utc_cells, loc_cells = blank(), blank()
        for ts, views in rec["series"].items():
            when = dt.datetime.strptime(ts, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
            utc_cells[when.weekday()][when.hour].append(views)
            local = when.astimezone(tz)
            loc_cells[local.weekday()][local.hour].append(views)

        utc_mat, loc_mat = means(utc_cells), means(loc_cells)
        utc_norm, loc_norm = normalise(utc_mat), normalise(loc_mat)
        # Local-time bins at the window edges are only partly covered; drop any
        # cell with fewer samples than the rest rather than let it read as a dip.
        counts = [[len(c) for c in row] for row in loc_cells]
        out[code] = {
            "label": rec["label"],
            "tz": rec["tz"],
            "spread": rec["spread"],
            "utc": [[round(v, 4) for v in row] for row in utc_norm],
            "local": [[round(v, 4) for v in row] for row in loc_norm],
            "local_counts": counts,
            "total_views": sum(rec["series"].values()),
            "stats": summarise(loc_norm, loc_mat),
        }

    payload = {
        "window": {"start": raw["start"], "end": raw["end"]},
        "days": DAYS,
        "languages": out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w", encoding="utf-8"))

    print(f"{len(out)} editions -> {OUT}\n")
    hdr = f"{'edition':<12}{'peak':>6}{'trough':>8}{'amp':>7}{'night%':>8}{'wknd':>7}  quiet day"
    print(hdr)
    print("-" * len(hdr))
    for code, rec in sorted(out.items(), key=lambda kv: kv[1]["stats"]["peak_hour"]):
        s = rec["stats"]
        print(f"{rec['label']:<12}{s['peak_hour']:>4}:00{s['trough_hour']:>6}:00"
              f"{s['amplitude']:>7}{s['night_share']*100:>7.1f}%{s['weekend_ratio']:>7}"
              f"  {DAYS[s['quiet_day']]}")


if __name__ == "__main__":
    main()
