"""
FlyRank Backend Track — W5 A9 — The polite scraper

Fetch -> extract -> normalize -> validate -> store -> report.
Downloads 3 catalogue pages from Books to Scrape (a public practice
sandbox), visits all ~60 book pages, and produces:
  - output/books.json    (validated records)
  - output/errors.json   (records/pages that failed, with reasons)
  - output/run-report.json (honest numbers about the run)
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import ValidationError

from schema import BookRecord, RawBookRecord

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_START = urljoin(BASE_URL, "catalogue/page-1.html")
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/darshanrvekhande-cpu/flyrank-scraper)"
TIMEOUT_SECONDS = 10
DELAY_SECONDS = 0.6
MAX_CATALOGUE_PAGES = 3

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


# ---------------------------------------------------------------------------
# Stage 1 — Fetch once, cache once
# ---------------------------------------------------------------------------

def cache_path_for(url: str) -> str:
    """Uses a short hash of the URL as the cache filename, so long book
    titles never hit Windows' ~260-character path limit."""
    import hashlib
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.html")


def fetch(url: str, stats: dict, allow_retry: bool = True) -> tuple[str | None, int | None]:
    """Fetches a URL politely, using the cache when available.

    Returns (html, status_code). html is None on failure.
    """
    cache_file = cache_path_for(url)

    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT {url} ({len(html)} bytes)")
        stats["cache_hits"] += 1
        return html, 200

    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        print(f"FETCH FAILED (network/timeout) {url}: {e}")
        if allow_retry:
            time.sleep(1)
            return fetch(url, stats, allow_retry=False)
        return None, None

    stats["pages_fetched"] += 1

    if response.status_code == 200:
        html = response.text
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"FETCH {url} status=200 ({len(html)} bytes)")
        time.sleep(DELAY_SECONDS)
        return html, 200

    # Retry once on 5xx, never on 404/403
    if 500 <= response.status_code < 600 and allow_retry:
        print(f"FETCH {url} status={response.status_code} — retrying once")
        time.sleep(1)
        return fetch(url, stats, allow_retry=False)

    print(f"FETCH {url} status={response.status_code} — not retrying")
    time.sleep(DELAY_SECONDS)
    return None, response.status_code


# ---------------------------------------------------------------------------
# Stage 2 — Find all three catalogue pages
# ---------------------------------------------------------------------------

def discover_book_urls(stats: dict) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    page_url = CATALOGUE_START
    pages_visited = 0

    while page_url and pages_visited < MAX_CATALOGUE_PAGES:
        html, status = fetch(page_url, stats)
        pages_visited += 1

        if html is None:
            print(f"Could not fetch catalogue page {page_url} (status={status}) — stopping discovery")
            break

        soup = BeautifulSoup(html, "html.parser")

        for h3 in soup.select("article.product_pod h3 a"):
            href = h3.get("href")
            if not href:
                continue
            absolute = urljoin(page_url, href)
            if absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)

        next_link = soup.select_one("li.next a")
        if next_link and pages_visited < MAX_CATALOGUE_PAGES:
            page_url = urljoin(page_url, next_link.get("href"))
        else:
            page_url = None

    stats["catalogue_pages"] = pages_visited
    stats["discovered"] = len(urls)
    stats["unique_urls"] = len(set(urls))
    print(f"catalogue_pages={pages_visited} discovered={len(urls)} unique_urls={len(set(urls))}")
    return urls


# ---------------------------------------------------------------------------
# Stage 3 — Extract the raw records
# ---------------------------------------------------------------------------

def extract_raw_record(book_url: str, source_page: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    product_main = soup.select_one("div.product_main")

    title = product_main.select_one("h1").get_text(strip=True)

    price_text = product_main.select_one("p.price_color").get_text(strip=True)

    availability_text = product_main.select_one("p.availability").get_text(strip=True)

    rating_tag = product_main.select_one("p.star-rating")
    rating_classes = rating_tag.get("class", []) if rating_tag else []
    rating_text = next((c for c in rating_classes if c in RATING_WORDS), "")

    description_tag = soup.select_one("#product_description ~ p")
    description = description_tag.get_text(strip=True) if description_tag else None

    return {
        "title": title,
        "product_url": book_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Stage 4 — Clean it, check it, store it
# ---------------------------------------------------------------------------

def normalize_price(price_text: str) -> float:
    cleaned = re.sub(r"[^\d.]", "", price_text)
    return float(cleaned)


def validate_and_clean(raw: dict) -> tuple[dict | None, dict | None]:
    """Returns (clean_record, error) — exactly one of them is not None."""
    try:
        RawBookRecord(**raw)  # confirms the raw shape is at least sane
        price_gbp = normalize_price(raw["price_text"])
        clean = {**raw, "price_gbp": price_gbp}
        validated = BookRecord(**clean)
        return json.loads(validated.model_dump_json()), None
    except (ValidationError, ValueError) as e:
        return None, {"record": raw, "reason": str(e)}


# ---------------------------------------------------------------------------
# Stage 5 — One bad page must not kill the run
# ---------------------------------------------------------------------------

def run() -> None:
    start_time = time.time()
    stats = {
        "pages_fetched": 0,
        "cache_hits": 0,
        "catalogue_pages": 0,
        "discovered": 0,
        "unique_urls": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "failed_pages": 0,
    }

    book_urls = discover_book_urls(stats)

    # Uncomment the next line to deliberately test failure handling
    # (Stage 5 checkpoint): a made-up URL that will 404.
    # book_urls.append(urljoin(BASE_URL, "catalogue/this-book-does-not-exist/index.html"))

    valid_records = []
    errors = []

    for book_url in book_urls:
        html, status = fetch(book_url, stats)

        if html is None:
            stats["failed_pages"] += 1
            errors.append({
                "url": book_url,
                "reason": f"fetch failed, status={status}",
            })
            continue

        try:
            raw = extract_raw_record(book_url, CATALOGUE_START, html)
        except Exception as e:
            stats["failed_pages"] += 1
            errors.append({"url": book_url, "reason": f"extraction failed: {e}"})
            continue

        clean, error = validate_and_clean(raw)
        if clean is not None:
            valid_records.append(clean)
            stats["valid_records"] += 1
        else:
            errors.append(error)
            stats["invalid_records"] += 1

    # De-duplicate by canonical URL (idempotent re-runs)
    dedup: dict[str, dict] = {}
    for record in valid_records:
        dedup[record["product_url"]] = record
    final_records = list(dedup.values())

    with open(os.path.join(OUTPUT_DIR, "books.json"), "w", encoding="utf-8") as f:
        json.dump(final_records, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, indent=2)

    duration = round(time.time() - start_time, 2)
    report = {
        "start_time": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
        "duration_seconds": duration,
        "catalogue_pages": stats["catalogue_pages"],
        "pages_fetched": stats["pages_fetched"],
        "cache_hits": stats["cache_hits"],
        "discovered_urls": stats["discovered"],
        "unique_urls": stats["unique_urls"],
        "valid_records": len(final_records),
        "invalid_records": stats["invalid_records"],
        "failed_pages": stats["failed_pages"],
    }

    with open(os.path.join(OUTPUT_DIR, "run-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n--- RUN REPORT ---")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
