"""
Extract per-article hourly pageviews for a watchlist from the Wikimedia dumps.

The REST API caps per-article granularity at daily, so hourly topic curves have
to come from the raw hourly dumps. Each line is
    domain_code page_title count_views total_response_size
and the file is sorted by domain_code, so the en / en.* blocks are contiguous:
we can skip decompressed output until the first `en ` line and stop reading the
stream entirely once the domain code no longer begins with `en`. That typically
avoids more than half the file.

Desktop (`en`) and mobile web (`en.m`) are summed; other en.* projects
(Wikibooks, Wikiquote, ...) are separate sites and are ignored.

Usage:  python src/fetch_pageview_dumps.py 2025-09-01 2025-09-07 [--workers N]
"""
import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
import zlib

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "..", "data", "raw")
# Which language edition to extract. The dump is sorted by domain code, so the
# chosen project's block is contiguous and the reader can stop once past it.
PROJECT = os.environ.get("CF_PROJECT", "en")
PB = PROJECT.encode()
NL = b"\n"
OUT = os.path.join(RAW, f"pageview_topics_{PROJECT}.jsonl")
UA = {"User-Agent": "circadian-fingerprint/1.0 (research; contact via github)"}
URL = ("https://dumps.wikimedia.org/other/pageviews/{y}/{y}-{m:02d}/"
       "pageviews-{y}{m:02d}{d:02d}-{h:02d}0000.gz")
CHUNK = 4 << 20

WANTED = None  # populated per process


def _load_wanted():
    global WANTED
    if WANTED is None:
        titles = json.load(open(os.path.join(RAW, f"top_articles_{PROJECT}.json"),
                                encoding="utf-8"))["titles"]
        WANTED = {t.encode("utf-8") for t in titles}
    return WANTED


def scan_block(block, counts, state):
    """Process newline-complete bytes. Returns updated state ('before'/'in'/'done')."""
    wanted = WANTED
    if state == "before":
        idx = block.find(NL + PB + b" ")
        if idx == -1:
            # Only the very first line of the file has no preceding newline.
            if not block.startswith(PB + b" "):
                return "before"
        else:
            block = block[idx + 1:]
        state = "in"
    for line in block.split(b"\n"):
        if not line:
            continue
        if not line.startswith(PB):
            # Sorted order: once past the project's prefix, the block is finished.
            return "done"
        parts = line.split(b" ")
        if len(parts) < 3:
            continue
        domain = parts[0]
        # Desktop and mobile web only; other sister projects share the prefix.
        if domain != PB and domain != PB + b".m":
            continue
        title = parts[1]
        if title in wanted:
            try:
                counts[title] += int(parts[2])
            except ValueError:
                pass
    return state


def fetch_hour(day, hour, retries=8):
    _load_wanted()
    y, m, d = day.year, day.month, day.day
    url = URL.format(y=y, m=m, d=d, h=hour)
    for attempt in range(retries):
        try:
            counts = collections.Counter()
            decomp = zlib.decompressobj(zlib.MAX_WBITS | 16)
            buf = b""
            state = "before"
            gz_bytes = 0
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as resp:
                while state != "done":
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    gz_bytes += len(chunk)
                    buf += decomp.decompress(chunk)
                    cut = buf.rfind(b"\n")
                    if cut == -1:
                        continue
                    block, buf = buf[: cut + 1], buf[cut + 1:]
                    state = scan_block(block, counts, state)
            if state != "done" and buf.strip():
                scan_block(buf, counts, state)
            return {
                "date": day.isoformat(), "hour": hour, "gz_bytes": gz_bytes,
                "stopped_early": state == "done",
                "counts": {k.decode("utf-8", "replace"): v for k, v in counts.items()},
            }
        except urllib.error.HTTPError as exc:
            # dumps.wikimedia.org asks for low concurrency and throttles hard.
            # Back off for tens of seconds rather than retrying immediately.
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(15 * (attempt + 1) + random.uniform(0, 5))
                continue
            if attempt == retries - 1:
                return {"date": day.isoformat(), "hour": hour, "error": repr(exc)}
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, zlib.error, OSError) as exc:
            if attempt == retries - 1:
                return {"date": day.isoformat(), "hour": hour, "error": repr(exc)}
            time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)

    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" not in r:
                done.add((r["date"], r["hour"]))

    jobs = []
    day = start
    while day <= end:
        for h in range(24):
            if (day.isoformat(), h) not in done:
                jobs.append((day, h))
        day += dt.timedelta(days=1)

    print(f"{len(done)} cached, {len(jobs)} to fetch", flush=True)
    t0 = time.time()
    n_ok = n_err = 0
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
            if i % 12 == 0 or i == len(futs):
                el = time.time() - t0
                print(f"{i}/{len(futs)}  ok={n_ok} err={n_err}  "
                      f"{i/el:.2f} hr/s  eta {(len(futs)-i)/(i/el)/60:.1f} min", flush=True)
    print(f"done in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
