# Circadian fingerprint of a platform

Activity on Wikipedia and GitHub, plotted as hour-of-day by day-of-week
heatmaps, per language edition and per topic.

Everything here is built from public bulk data. No API keys, no BigQuery
billing, no credentials.

## What it finds

**Wikipedia reading is a clock, not a calendar.** Across 23 language editions
and 11.7 billion pageviews, hour-of-day swings activity by up to 11.7x while
day-of-week moves it by barely 10%. Shown in UTC, the 23 editions look like 23
unrelated signals whose peaks span 12 hours. Shifted to each edition's dominant
local timezone, 21 of the 23 peak between 20:00 and 22:00.

**Amplitude measures geography, not enthusiasm.** Editions read inside a single
timezone swing hard (Dutch 11.7x, German 11.5x, Italian 11.5x). Editions whose
readers are scattered across longitudes flatten out, because one group's night
is another's afternoon (English 1.7x, Arabic 2.7x, Spanish 3.0x). The amplitude
of the daily curve is a readout of how concentrated the audience is.

**GitHub is the opposite organism.** Its weekly cycle is strong where
Wikipedia's is flat: the number of distinct people reviewing pull requests falls
to 30% of its weekday level at weekends. Its hour-of-day curve, by contrast,
swings only 1.66x, which is almost exactly English Wikipedia's 1.67x. Both are
globally distributed populations measured on a single clock, and both flatten
for the same reason.

**Counting events would have measured robots.** In one sampled hour the ten
busiest accounts produced 24.8% of all pushes, and several of the heaviest
carried no `[bot]` suffix. The pipeline therefore counts *distinct accounts
active per hour* rather than events.

**On a global platform, "what gets read at 3am" mostly means "who is awake".**
Ranking English Wikipedia articles by when they are read returns Philippine,
Indian and Vietnamese subjects at one end and American and British ones at the
other. It is a longitude detector, not a mood ring.

**Day of week survives what hour of day cannot.** Timezones shift the clock but
not the calendar, so the weekend index is the one axis where a difference
between two articles is a difference about the articles. Sorting 3,100 English
articles by it separates sport and entertainment from news and institutions with
no topic labels anywhere in the pipeline. The cleanest check: *Thursday Night
Football* scores 0.20, with a daily curve of 0.38, 0.45, 0.50, **1.93**,
**3.22**, 0.25, 0.27 from Monday to Sunday. Nobody told the pipeline when the
game is played.

**Pointed at a single-timezone edition, the hour axis finally works.** Japanese
Wikipedia's readers are overwhelmingly in one country on one timezone with no
daylight saving, so JST is a real clock. Its quiet window sits at 02:00 to 07:00
JST, actual night, rather than English Wikipedia's 06:00 to 11:00 UTC, which is
nobody's night in particular. And the afternoon list is startlingly coherent:
**seventeen of the top twenty-four articles read between 2pm and 7pm JST are
sumo** - wrestlers, a commentator, the list of champions, the article on prize
banners - peaking at 17:00 and 18:00, just as the September grand tournament's
top division finishes on television. Nothing in the pipeline knows what sumo is
or when the tournament was; it reconstructed a broadcast schedule from hourly
counts. The 2am to 7am list is dominated by adult-industry subjects, with
late-night anime and idol groups behind them.

## Data sources

> The raw inputs are not in this repository. [DATA.md](DATA.md) records exactly which files were used, with sizes and fingerprints, and how to re-fetch them.

| Source | What it gives | Why |
|---|---|---|
| [Wikimedia Pageviews API](https://wikimedia.org/api/rest_v1/) | hourly totals per language edition | the only endpoint with hourly granularity; the per-article endpoint caps at daily |
| [Wikimedia pageview dumps](https://dumps.wikimedia.org/other/pageviews/) | hourly views per article | needed for per-topic curves, since the API will not serve them |
| [GH Archive](https://www.gharchive.org/) | every public GitHub event, one file per hour | free HTTP download, no BigQuery billing |

Window: 1 to 28 September 2025 throughout.

## Running it

```bash
python src/fetch_wikipedia.py 2025-09-01 2025-09-28
python src/analyze_wikipedia.py

python src/fetch_gharchive.py 2025-09-01 2025-09-28 --workers 12
python src/analyze_github.py

python src/fetch_top_articles.py
CF_PROJECT=ja python src/fetch_top_articles.py
python src/fetch_pageview_dumps.py 2025-09-01 2025-09-14 --workers 2
CF_PROJECT=ja python src/fetch_pageview_dumps.py 2025-09-01 2025-09-14 --workers 2
python src/analyze_topics.py
CF_PROJECT=ja CF_TZ_OFFSET=9 CF_TZ_LABEL=JST CF_MIN_VIEWS=3000 python src/analyze_topics.py

python src/build_site.py
```

All fetchers cache to `data/raw/` and resume, so an interrupted run picks up
where it stopped.

## How the heavy parts stay cheap

The pipeline reads 106.7 GB of compressed public data: 54.9 GB of GH Archive
and 51.9 GB of pageview dumps. Two things keep that tractable on a laptop:

**No JSON parsing for GitHub.** Each GH Archive file covers exactly one UTC
hour, so the filename supplies the timestamp. `type` and `actor.login` sit
adjacent at the head of every record, so one regex pass over the decompressed
bytes yields the joint distribution of event type and bot status exactly. A
check against a hand-parsed hour matched to the event: 165,169 lines,
92,921 pushes.

**Early exit for Wikipedia.** The pageview dumps are sorted by domain code, so
one project's block is contiguous. The reader stops as soon as the domain code
no longer matches, which reads 49% of each file for `en` and 73% for `ja`.

Processes rather than threads: decompression releases the GIL but the regex
scan does not, so threads capped out at 1.4x regardless of core count.

## Checking it

`bash src/verify.sh` runs the lot: build, JS syntax, theme-token completeness,
chart-palette gates, and a headless render of the chart code against the real
payload.

The palette check is the one worth explaining. Colourblind separation is
computable, so it is computed rather than eyeballed: `check_palette.py`
simulates protanopia, deuteranopia and tritanopia (Vienot/Brettel/Mollon
projection in linear LMS) and holds every pair of series colours to an OKLab
dE of 8 under simulation and 15 for normal vision, plus 3:1 contrast against
its own surface. It caught a real defect: in dark mode the original blue and
aqua collapsed to dE 1.5 under tritanopia, which is indistinguishable. Both
themes now pass with the worst pair at 11.7 (light) and 11.1 (dark).

## Caveats

- GH Archive carries no location, so its clock is UTC only. There is no
  local-time view of GitHub here, and its hourly amplitude is damped by the same
  longitude-mixing that flattens English Wikipedia.
- Mapping a language edition to one timezone is exact for editions like
  Japanese or Polish and rough for English, Spanish, Arabic, Portuguese and
  Russian. Those five are flagged in `src/languages.py` and marked on the
  charts. The flags were set before the analysis ran, not fitted to it.
- Article rankings drop anything whose views pile into one or two days, so a
  single news spike cannot define a curve. Patterns have to repeat to count.
- Topic curves rest on four weeks, so each weekday occurs four times. That is
  enough to separate rugby from earthquakes; it is still not enough to trust a
  small difference between two individual articles.
- The Japanese category counts in the 2am to 7am list were read by hand off the
  top thirty, not assigned by a classifier.
- GH Archive's 2026 files are incomplete (a sampled hour held 2,248 events and
  no PushEvents at all), which is why the window is September 2025.

## Layout

```
src/
  languages.py             editions profiled, with dominant timezone
  event_groups.py          GitHub event type groupings
  fetch_wikipedia.py       hourly totals per edition, from the API
  fetch_gharchive.py       hourly GitHub events, counted without parsing JSON
  fetch_top_articles.py    the article watchlist, unioned from daily top-1000s
  fetch_pageview_dumps.py  per-article hourly views, from the bulk dumps
  analyze_wikipedia.py     weekday x hour fingerprints, UTC and local
  analyze_github.py        same, by event type and by bot vs human
  analyze_topics.py        per-article curves, indexed against the baseline
  build_site.py            assembles site/data.js and concatenates index.html
  serve.py                 local preview, wrapped in the artifact's own skeleton
  verify.sh                runs every check below
  check_js.py              node --check on each embedded script block
  check_tokens.py          every CSS var used must exist in the bare :root
  check_palette.py         CVD separation and contrast gates for chart colours
  smoke_dom.js             runs the chart code headless against the real payload
site/                      the page, assembled from the _*.html parts
data/raw/                  cached downloads (gitignored)
data/processed/            analysis output
```
