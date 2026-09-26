# The Polite Scraper (W5 · A9)
_Last verified: 2026-09-26 — clean run produced exactly 60 records, 
zero failures._

A small scraping pipeline: **fetch → extract → normalize → validate → store → report**.
Downloads the first 3 catalogue pages of [Books to Scrape](https://books.toscrape.com), visits all ~60 book pages, and produces clean, schema-validated JSON — politely, and without crashing on a broken page.

## Target classification (Stage 0)

- **Site:** [books.toscrape.com](https://books.toscrape.com) — a public sandbox built explicitly for practicing web scraping ("A fictional bookstore that desperately wants to be scraped. It's a safe place for beginners learning web scraping...").
- **Scope:** only the first 3 catalogue pages (~60 books). Nothing beyond that is touched.
- **Data collected:** title, price, availability, star rating, description, and the canonical product URL for each book.
- **`robots.txt` check:** requested `https://books.toscrape.com/robots.txt` once — returned 404 Not Found (no robots file found).
- **Why this is appropriate here:** the site exists specifically as a scraping practice target, at low volume (60 records), with no login, paywall, or personal data involved.

**I will not reuse this code on another site without checking its rules and terms first.**

## Setup and run

```bash
cd scraper
pip install -r requirements.txt
python src/main.py
```

This produces:
- `output/books.json` — validated records
- `output/errors.json` — any records/pages that failed, with reasons
- `output/run-report.json` — honest numbers about the run (see below)

Run it twice — the second run mostly hits the cache (`cache/` folder) and produces the exact same 60 records, not 120.

## Record schema

Each entry in `books.json`:

```json
{
  "title": "A Light in the Attic",
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "price_text": "£51.77",
  "price_gbp": 51.77,
  "availability_text": "In stock (22 available)",
  "rating_text": "Three",
  "description": "...",
  "source_page": "https://books.toscrape.com/catalogue/page-1.html",
  "fetched_at": "2026-09-25T10:00:00+00:00"
}
```

`price_gbp` is the cleaned numeric price; `price_text` is kept alongside it as the original raw value. `product_url` is each record's canonical identity — duplicates are removed by this URL.

## Politeness rules followed

- **User-agent:** every request identifies itself as `FlyRankInternshipA9/1.0 (+link-to-repo)`, never a browser-spoofing string.
- **Timeout:** every request gives up after 10 seconds rather than hanging forever.
- **Delay:** at least 0.6 seconds between real requests to the site. Cached pages need no delay — they never leave the machine.
- **Cache:** every fetched page is saved to `cache/` and re-read from there on subsequent runs, so the site is only asked once per page during development.
- **Retry rules:** a `5xx` server error or timeout is retried once; a `404` or `403` is never retried (asking again won't create a missing page, and retrying a block is how a polite robot becomes a pest).

## Run report (Stage 5 proof)

This is a real `output/run-report.json` from a run with one deliberately broken URL added to the book list — the run still finished, all 60 good records still made it into `books.json`, and the broken page was logged and skipped:

```json
{
  "start_time": "2026-09-26T07:27:25.259741+00:00",
  "duration_seconds": 2.75,
  "catalogue_pages": 3,
  "pages_fetched": 1,
  "cache_hits": 63,
  "discovered_urls": 60,
  "unique_urls": 60,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1
}
```

## Why this assignment needed no browser

Every field this scraper collects (title, price, availability, rating, description) is already present in the raw HTML the server sends back — none of it is injected by JavaScript after the page loads. Viewing the page source directly shows all the data needed, so a full browser (like Playwright) would only add startup cost and memory overhead for zero additional data.

## Ethics note

This scraper only touches a site built specifically for scraping practice, at a small, fixed scope (60 records), with an honest identifying user-agent and a polite delay between requests. In general: use an official API when one exists rather than scraping; never bypass logins, paywalls, or explicit blocks; and only collect the data actually needed for the task at hand — not everything a page happens to expose.

## Known limitation

Rating is currently extracted from the CSS class name (`star-rating Three`, etc.) rather than a more robust attribute, so it would break if the site ever changed its markup convention for star ratings.
