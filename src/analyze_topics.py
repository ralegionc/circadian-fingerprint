"""
Rank articles by when they are read, relative to that edition's own rhythm.

Run per project:
    CF_PROJECT=en CF_TZ_OFFSET=0 python src/analyze_topics.py
    CF_PROJECT=ja CF_TZ_OFFSET=9 python src/analyze_topics.py

Two things have to be handled or the ranking measures the wrong thing.

1. News spikes. A first pass returned articles like Teachers' Day and a string
   of US Open players: each had one enormous day, and the hour of that single
   burst set its whole profile. So an article's curve is built as the *median
   across days* of its day-normalised hourly profile, and articles whose views
   pile into one or two days are dropped. A pattern has to repeat to count.

2. The overall daily cycle. Everything rises and falls together, so each article
   is indexed against the aggregate curve built the same way:

       index_a(h) = a's median daily share of hour h
                  / the whole watchlist's median daily share of hour h

   1.0 means the article moves exactly with everything else.

The timezone offset is what makes the hour axis mean anything. On en.wikipedia
readers are spread across every longitude, so "read at 3am" cannot be defined --
the hour axis there separates audiences by geography more than by subject. On
ja.wikipedia essentially all readers sit in one zone (JST, UTC+9, no daylight
saving), so shifting the clock by nine hours gives a genuine local time and
"read at 3am" means what it says.
"""
import collections
import datetime as dt
import json
import os
import statistics

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "..", "data", "raw")
PROC = os.path.join(HERE, "..", "data", "processed")

PROJECT = os.environ.get("CF_PROJECT", "en")
TZ_OFFSET = int(os.environ.get("CF_TZ_OFFSET", "0"))
TZ_LABEL = os.environ.get("CF_TZ_LABEL", "UTC" if TZ_OFFSET == 0 else f"UTC+{TZ_OFFSET}")
MIN_VIEWS = int(os.environ.get("CF_MIN_VIEWS", "20000"))

IN = os.path.join(RAW, f"pageview_topics_{PROJECT}.jsonl")
OUT = os.path.join(PROC, f"topic_fingerprints_{PROJECT}.json")

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

MIN_DAYS = 8           # a pattern has to show up on this many days
MAX_DAY_SHARE = 0.30   # drop anything that is really one news event
MIN_DAY_VIEWS = 200    # a day too small to shape a 24-hour profile
TOP_N = 30


def profile(day_vectors, slots=24):
    """Median across days of each day's own normalised profile."""
    per_day = []
    for vec in day_vectors:
        s = sum(vec)
        if s >= MIN_DAY_VIEWS:
            per_day.append([v / s for v in vec])
    if len(per_day) < 2:
        return None
    med = [statistics.median(d[i] for d in per_day) for i in range(slots)]
    tot = sum(med)
    return [v / tot for v in med] if tot else None


def main():
    recs = {}
    for line in open(IN, encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "error" not in r:
            recs[(r["date"], r["hour"])] = r
    recs = list(recs.values())
    if not recs:
        print(f"no records in {IN}")
        return

    utc_hours = {(r["date"], r["hour"]) for r in recs}

    # article -> local date -> [24 local hours]
    hourly = collections.defaultdict(lambda: collections.defaultdict(lambda: [0] * 24))
    totals = collections.Counter()
    local_cover = collections.Counter()

    for r in recs:
        when = dt.datetime.strptime(r["date"], "%Y-%m-%d").replace(hour=r["hour"])
        local = when + dt.timedelta(hours=TZ_OFFSET)
        ld, lh = local.date().isoformat(), local.hour
        local_cover[ld] += 1
        for title, v in r["counts"].items():
            hourly[title][ld][lh] += v
            totals[title] += v

    # Only local days assembled from all 24 source hours can carry a daily total.
    full_days = sorted(d for d in local_cover if local_cover[d] == 24)
    wd_of = {d: dt.date.fromisoformat(d).weekday() for d in full_days}
    daily = {t: {d: sum(hourly[t][d]) for d in full_days} for t in totals}

    keep = []
    for t, n in totals.items():
        if n < MIN_VIEWS:
            continue
        dd = daily[t]
        if sum(1 for v in dd.values() if v > 0) < MIN_DAYS:
            continue
        tot = sum(dd.values())
        if not tot or max(dd.values()) / tot > MAX_DAY_SHARE:
            continue
        keep.append(t)
    keep.sort(key=lambda t: -totals[t])

    agg_hour = collections.defaultdict(lambda: [0] * 24)
    for t in keep:
        for d in full_days:
            row = hourly[t][d]
            for h in range(24):
                agg_hour[d][h] += row[h]
    base_hour = profile([agg_hour[d] for d in full_days])
    if not base_hour:
        print(f"not enough complete local days yet ({len(full_days)})")
        return

    def weekday_index(get_total):
        per_wd = collections.defaultdict(list)
        for d in full_days:
            per_wd[wd_of[d]].append(get_total(d))
        if any(not per_wd.get(i) for i in range(7)):
            return None
        means = [statistics.mean(per_wd[i]) for i in range(7)]
        avg = sum(means) / 7
        return [m / avg for m in means] if avg else None

    base_day = weekday_index(lambda d: sum(agg_hour[d]))

    best = min(range(24), key=lambda s: sum(base_hour[(s + k) % 24] for k in range(6)))
    quiet_hours = [(best + k) % 24 for k in range(6)]
    busy_hours = [(best + 12 + k) % 24 for k in range(6)]

    out = {}
    for t in keep:
        ph = profile([hourly[t][d] for d in full_days])
        if not ph:
            continue
        idx_h = [ph[i] / base_hour[i] if base_hour[i] else 0.0 for i in range(24)]
        night = sum(idx_h[h] for h in quiet_hours) / 6
        dayi = sum(idx_h[h] for h in busy_hours) / 6
        rec = {
            "views": totals[t],
            "idx_hour": [round(v, 4) for v in idx_h],
            "nocturnality": round(night / dayi, 4) if dayi else None,
            "peak_hour": max(range(24), key=lambda h: idx_h[h]),
        }
        wd = weekday_index(lambda d, t=t: daily[t][d])
        if wd and base_day:
            idx_d = [wd[i] / base_day[i] if base_day[i] else 0.0 for i in range(7)]
            rec["idx_day"] = [round(v, 4) for v in idx_d]
            wknd = (idx_d[5] + idx_d[6]) / 2
            wkdy = sum(idx_d[0:5]) / 5
            rec["weekendness"] = round(wknd / wkdy, 4) if wkdy else None
        out[t] = rec

    def rank_by(field):
        return sorted((t for t in out if out[t].get(field)),
                      key=lambda t: -out[t][field])

    rn, rw = rank_by("nocturnality"), rank_by("weekendness")
    payload = {
        "project": PROJECT,
        "tz_offset": TZ_OFFSET,
        "tz_label": TZ_LABEL,
        "hours_ingested": len(utc_hours),
        "full_days": full_days,
        "days": DAYS,
        "filters": {"min_views": MIN_VIEWS, "min_days": MIN_DAYS,
                    "max_day_share": MAX_DAY_SHARE},
        "articles_kept": len(out),
        "baseline_hour": [round(v, 5) for v in base_hour],
        "baseline_day": [round(v, 5) for v in base_day] if base_day else None,
        "quiet_hours": quiet_hours,
        "busy_hours": busy_hours,
        "articles": out,
        "rank": {"nocturnal": rn[:TOP_N], "diurnal": rn[::-1][:TOP_N],
                 "weekend": rw[:TOP_N], "weekday": rw[::-1][:TOP_N]},
    }
    os.makedirs(PROC, exist_ok=True)
    json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

    print(f"[{PROJECT}] {len(utc_hours)} hours, {len(full_days)} full local days "
          f"({TZ_LABEL}), {len(out)} articles kept -> {OUT}")
    print(f"quiet {TZ_LABEL} hours {quiet_hours}   busy {busy_hours}\n")
    for name in ("nocturnal", "diurnal", "weekend", "weekday"):
        field = "nocturnality" if name in ("nocturnal", "diurnal") else "weekendness"
        if not payload["rank"][name]:
            continue
        print(f"--- most {name} ---")
        for t in payload["rank"][name][:14]:
            print(f"  {out[t][field]:>6.2f}  {t[:50]:<50} {out[t]['views']:>9,}")
        print()


if __name__ == "__main__":
    main()
