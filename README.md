# The Polite Scraper (W5 · A9)

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

##