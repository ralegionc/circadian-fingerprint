"""
Ingest GH Archive hourly event dumps and reduce them to per-hour counts.

Each GH Archive file covers exactly one UTC hour, so the filename supplies the
timestamp and there is no need to parse `created_at` -- or any JSON at all.
Events are newline-delimited and the `type` / `actor.login` fields sit adjacent
at the head of every record, so a single regex pass over the decompressed bytes
yields the joint distribution of (event type, is-bot) exactly.

Usage:  python src/fetch_gharchive.py 2025-09-01 2025-09-28 [--workers N]
"""
import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from event_groups import TYPE_TO_GROUP, GROUP_NAMES, HEAVY_THRESHOLD

UA = {"User-Agent": "circadian-fingerprint/1.0 (research; contact via github)"}
BASE = "https://data.gharchive.org/{date}-{hour}.json.gz"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "gharchive_hours.jsonl")
CHUNK = 4 << 20  # 4 MiB of compressed input per read

# `"type":"XEvent","actor":{"id":N,"login":"..."` -- matches once per event.
EVENT_RE = re.compile(rb'"type":"(\w+Event)","actor":\{"id":\d+,"login":"([^"]*)"')


def scan(blob, counts, actors, per_actor):
    """Accumulate counts and distinct-actor sets for one newline-complete block.

    Raw event counts measure automation more than people: in a sample hour the
    ten busiest accounts produced a quarter of all pushes, and several of the
    heaviest carried no [bot] suffix. So alongside events we collect the set of
    distinct logins per group, which is what "how many people were active" needs.
    """
    for m in EVENT_RE.finditer(blob):
        etype = m.group(1)
        login = m.group(2)
        is_bot = login.endswith(b"[bot]")
        counts[(etype, is_bot)] += 1
        group = TYPE_TO_GROUP.get(etype)
        if group is not None:
            actors[(group, is_bot)].add(login)
        actors[("ALL", is_bot)].add(login)
        if not is_bot:
            per_actor[login] += 1


def fetch_hour(date, hour, retries=4):
    url = BASE.format(date=date, hour=hour)
    for attempt in range(retries):
        try:
            counts = collections.Counter()
            actors = collections.defaultdict(set)
            per_actor = collections.Counter()
            lines = 0
            gz_bytes = 0
            decomp = zlib.decompressobj(zlib.MAX_WBITS | 16)
            buf = b""
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as resp:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    gz_bytes += len(chunk)
                    buf += decomp.decompress(chunk)
                    cut = buf.rfind(b"\n")
                    if cut == -1:
                        continue
                    block, buf = buf[: cut + 1], buf[cut + 1 :]
                    lines += block.count(b"\n")
                    scan(block, counts, actors, per_actor)
            buf += decomp.flush()
            if buf.strip():
                lines += 1
                scan(buf, counts, actors, per_actor)
            heavy = {a: n for a, n in per_actor.items() if n >= HEAVY_THRESHOLD}
            return {
                "date": date,
                "hour": hour,
                "lines": lines,
                "gz_bytes": gz_bytes,
                "counts": {f"{k[0].decode()}|{int(k[1])}": v for k, v in counts.items()},
                "actors": {f"{g}|{int(b)}": len(s) for (g, b), s in actors.items()},
                "heavy_actors": len(heavy),
                "heavy_events": sum(heavy.values()),
                "human_events": sum(per_actor.values()),
            }
        except (urllib.error.URLError, zlib.error, OSError) as exc:
            if attempt == retries - 1:
                return {"date": date, "hour": hour, "error": repr(exc)}
            time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)

    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "error" not in rec:
                    done.add((rec["date"], rec["hour"]))

    jobs = []
    day = start
    while day <= end:
        for hour in range(24):
            if (day.isoformat(), hour) not in done:
                jobs.append((day.isoformat(), hour))
        day += dt.timedelta(days=1)

    print(f"{len(done)} hours cached, {len(jobs)} to fetch", flush=True)
    t0 = time.time()
    n_ok = n_err = 0
    # Processes, not threads: decompression releases the GIL but the regex scan
    # does not, so threads cap out around 1.4x regardless of core count.
    with open(OUT, "a", encoding="utf-8") as fh, cf.ProcessPoolExecutor(args.workers) as ex:
        futs = [ex.submit(fetch_hour, d, h) for d, h in jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            rec = fut.result()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if "error" in rec:
                n_err += 1
                print(f"  ERROR {rec['date']}-{rec['hour']}: {rec['error']}", flush=True)
            else:
                n_ok += 1
            if i % 24 == 0 or i == len(futs):
                el = time.time() - t0
                rate = i / el
                print(
                    f"{i}/{len(futs)} hours  ok={n_ok} err={n_err}  "
                    f"{rate:.2f} hr/s  eta {(len(futs)-i)/rate/60:.1f} min",
                    flush=True,
                )
    print(f"done in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
