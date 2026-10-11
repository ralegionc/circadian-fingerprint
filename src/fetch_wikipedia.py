"""
Fetch hourly aggregate pageviews per Wikipedia language edition.

The REST API offers hourly granularity on the *aggregate* endpoint only; the
per-article endpoint tops out at daily, which is why the topic dimension in this
project comes from GH Archive rather than from Wikipedia articles.

agent=user filters out the self-identified crawler traffic that would otherwise
flatten the daily cycle.

Usage:  python src/fetch_wikipedia.py 2025-09-01 2025-09-28
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from languages import LANGUAGES

UA = {"User-Agent": "circadian-fingerprint/1.0 (research; contact via github)"}
URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/"
       "{proj}/all-access/user/hourly/{start}/{end}")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "wikipedia_hourly.json")


def fetch(proj, start, end, retries=4):
    url = URL.format(proj=proj, start=start, end=end)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)["items"]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            if exc.code == 429:
                # The analytics API throttles aggressively; back off hard.
                time.sleep(20 * (attempt + 1))
                continue
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, OSError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--retries", type=int, default=6)
    args = ap.parse_args()

    start = dt.date.fromisoformat(args.start).strftime("%Y%m%d") + "00"
    # The API end bound is inclusive, so ask for the last hour of the end day.
    end = dt.date.fromisoformat(args.end).strftime("%Y%m%d") + "23"

    cache_dir = os.path.join(os.path.dirname(OUT), "wiki_cache")
    os.makedirs(cache_dir, exist_ok=True)

    out = {}
    for code, label, tz, spread in LANGUAGES:
        proj = f"{code}.wikipedia"
        cache = os.path.join(cache_dir, f"{code}_{args.start}_{args.end}.json")
        if os.path.exists(cache):
            items = json.load(open(cache, encoding="utf-8"))
        else:
            items = fetch(proj, start, end, retries=args.retries)
            if items:
                json.dump(items, open(cache, "w", encoding="utf-8"))
        if not items:
            print(f"  {proj}: NO DATA", flush=True)
            continue
        out[code] = {
            "label": label,
            "tz": tz,
            "spread": spread,
            "series": {it["timestamp"]: it["views"] for it in items},
        }
        total = sum(it["views"] for it in items)
        print(f"  {proj}: {len(items)} hours, {total/1e6:.1f}M views", flush=True)
        time.sleep(2.0)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"start": args.start, "end": args.end, "projects": out}, fh)
    print(f"wrote {OUT} ({len(out)} projects)", flush=True)


if __name__ == "__main__":
    main()
