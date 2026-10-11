"""
Build the article watchlist for the topic fingerprints.

Rather than hand-picking "3am articles" and "Monday articles" -- which would let
the conclusion pick its own evidence -- take the top 1000 en.wikipedia articles
on each of several days and union them. Which of those turn out nocturnal is
then a finding rather than a selection.
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(__file__)
PROJECT = os.environ.get("CF_PROJECT", "en")
OUT = os.path.join(HERE, "..", "data", "raw", f"top_articles_{PROJECT}.json")
UA = {"User-Agent": "circadian-fingerprint/1.0 (research; contact via github)"}
URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
       "{proj}.wikipedia/all-access/{y}/{m:02d}/{d:02d}")

# Spread across all seven weekdays so a weekday-specific spike cannot dominate.
DAYS = [dt.date(2025, 9, d) for d in (2, 5, 8, 11, 14, 17, 20, 23, 26, 28)]

SKIP_PREFIXES = ("Special:", "Wikipedia:", "Portal:", "Help:", "Category:",
                 "Template:", "File:", "Talk:", "User:", "Draft:",
                 "特別:", "Wikipedia：", "カテゴリ:",
                 "ファイル:", "テンプレート:")
SKIP_EXACT = {"Main_Page", "-", "Hyphen-minus",
              "メインページ", "特別:検索"}


def main():
    seen = {}
    for day in DAYS:
        url = URL.format(proj=PROJECT, y=day.year, m=day.month, d=day.day)
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=90) as resp:
                    arts = json.load(resp)["items"][0]["articles"]
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    time.sleep(20 * (attempt + 1))
                    continue
                print(f"  {day}: HTTP {exc.code} for {url}", flush=True)
                arts = []
                break
        kept = 0
        for a in arts:
            t = a["article"]
            if t in SKIP_EXACT or t.startswith(SKIP_PREFIXES):
                continue
            seen[t] = seen.get(t, 0) + a["views"]
            kept += 1
        print(f"  {day}: {kept} articles kept, {len(seen)} unique so far", flush=True)
        time.sleep(2)

    titles = sorted(seen)
    json.dump({"days": [d.isoformat() for d in DAYS],
               "titles": titles,
               "views_sum": seen}, open(OUT, "w", encoding="utf-8"))
    print(f"\n{len(titles)} unique titles -> {OUT}")


if __name__ == "__main__":
    main()
