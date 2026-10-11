"""
Assemble the processed datasets into the page payload, then build index.html.

The payload is emitted as `site/data.js` assigning a global rather than a .json
fetched at runtime: the artifact sandbox serves same-origin scripts reliably,
and it keeps index.html free of a half-megabyte inline blob.

The topic sets are the only ones needing thinning. Full hourly curves for every
article would dominate the payload, so each article contributes its two summary
coordinates for the scatter while only the ranked extremes carry their curves.

index.html is concatenated from the site/_*.html parts in a fixed order so the
markup, the chart engine and the wiring can be edited separately.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "..", "data", "processed")
SITE = os.path.join(HERE, "..", "site")
DATA_JS = os.path.join(SITE, "data.js")
INDEX = os.path.join(SITE, "index.html")

PARTS = ["_style.html", "_components.html", "_body.html", "_body2.html",
         "_body3.html", "_body4.html", "_body5.html",
         "@data", "_script.html", "_init.html"]


def load(name):
    path = os.path.join(PROC, name)
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def pack_topics(topics):
    arts = topics["articles"]
    detailed = {t for lst in topics["rank"].values() for t in lst}
    return {
        "project": topics["project"],
        "tz_label": topics["tz_label"],
        "hours": topics["hours_ingested"],
        "full_days": len(topics["full_days"]),
        "days": topics["days"],
        "filters": topics["filters"],
        "articles_kept": topics["articles_kept"],
        "baseline_hour": topics["baseline_hour"],
        "baseline_day": topics["baseline_day"],
        "quiet_hours": topics["quiet_hours"],
        "busy_hours": topics["busy_hours"],
        "rank": topics["rank"],
        "scatter": [
            [t, a["nocturnality"], a["weekendness"], a["views"]]
            for t, a in arts.items()
            if a.get("nocturnality") and a.get("weekendness")
        ],
        "detail": {
            t: {k: arts[t][k] for k in
                ("idx_hour", "idx_day", "views", "nocturnality",
                 "weekendness", "peak_hour") if k in arts[t]}
            for t in detailed if t in arts
        },
    }


def main():
    wiki = load("wikipedia_fingerprints.json")
    gh = load("github_fingerprints.json")

    payload = {"wiki": None, "github": None, "topics": {}}

    if wiki:
        payload["wiki"] = {
            "window": wiki["window"],
            "days": wiki["days"],
            "languages": {
                c: {"label": r["label"], "tz": r["tz"], "spread": r["spread"],
                    "utc": r["utc"], "local": r["local"],
                    "total_views": r["total_views"], "stats": r["stats"]}
                for c, r in wiki["languages"].items()
            },
        }

    if gh:
        payload["github"] = {
            "hours": gh["hours_ingested"],
            "total_events": gh["total_events"],
            "days": gh["days"],
            "heavy_threshold": gh["heavy_threshold"],
            "actors": gh["actors"],
            "events": gh["events"],
            "automation": gh["automation"],
        }

    for proj in ("en", "ja"):
        t = load(f"topic_fingerprints_{proj}.json")
        if t:
            payload["topics"][proj] = pack_topics(t)
    if not payload["topics"]:
        payload["topics"] = None

    os.makedirs(SITE, exist_ok=True)
    with open(DATA_JS, "w", encoding="utf-8") as fh:
        fh.write("window.CIRCADIAN = ")
        json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
        fh.write(";\n")

    chunks = []
    for part in PARTS:
        if part == "@data":
            # Inlined rather than linked: the payload is small enough, and a
            # single self-contained file renders anywhere, including local
            # file:// previews that will not fetch a sibling script.
            chunks.append("<script>\n" + open(DATA_JS, encoding="utf-8").read()
                          + "</script>")
            continue
        path = os.path.join(SITE, part)
        if not os.path.exists(path):
            raise SystemExit(f"missing part: {part}")
        chunks.append(open(path, encoding="utf-8").read().rstrip())
    html = "\n\n".join(chunks) + "\n"
    open(INDEX, "w", encoding="utf-8", newline="\n").write(html)

    left = [tok for tok in ("{{", "}}") if tok in html]
    have = [k for k, v in payload.items() if v]
    print(f"data.js  {os.path.getsize(DATA_JS)/1024:>7.0f} KB   sections: {', '.join(have)}")
    if payload["topics"]:
        print(f"          topics: {', '.join(payload['topics'])}")
    print(f"index.html {os.path.getsize(INDEX)/1024:>5.0f} KB")
    if left:
        import re
        print("UNFILLED PLACEHOLDERS:", sorted(set(re.findall(r"\{\{\w+\}\}", html))))


if __name__ == "__main__":
    main()
