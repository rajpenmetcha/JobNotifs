"""Poll SimplifyJobs/New-Grad-Positions for new job postings and notify Discord."""
import json
import os
import sys
import time

import requests

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions"
    "/dev/.github/scripts/listings.json"
)
SEEN_FILE = "seen_ids.json"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DRY_RUN = bool(os.environ.get("DRY_RUN"))

# Only post jobs whose title contains one of these (case-insensitive). Empty = no filter.
TITLE_KEYWORDS = []

EMBED_COLOR = 0x5865F2  # Discord blurple
MAX_EMBEDS_PER_MESSAGE = 10


def fetch_listings():
    last_err = None
    for _ in range(2):
        try:
            resp = requests.get(LISTINGS_URL, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_err = e
            time.sleep(3)
    raise SystemExit(f"Failed to fetch listings after retry: {last_err}")


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return None  # signals first run
    with open(SEEN_FILE) as f:
        return set(json.load(f))


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)
        f.write("\n")


def eligible(row):
    if not (row.get("active") and row.get("is_visible")):
        return False
    if TITLE_KEYWORDS:
        title = (row.get("title") or "").lower()
        if not any(k.lower() in title for k in TITLE_KEYWORDS):
            return False
    return True


def build_embed(row):
    fields = [
        {"name": "Company", "value": row.get("company_name") or "Unknown", "inline": True},
        {"name": "Location", "value": ", ".join(row.get("locations") or []) or "Unknown", "inline": True},
        {"name": "Sponsorship", "value": row.get("sponsorship") or "Unknown", "inline": True},
    ]
    date_posted = row.get("date_posted")
    if date_posted:
        fields.append({"name": "Date Posted", "value": f"<t:{int(date_posted)}:R>", "inline": True})
    return {
        "title": (row.get("title") or "Untitled")[:256],
        "url": row.get("url"),
        "color": EMBED_COLOR,
        "fields": fields,
    }


def post_to_discord(embeds):
    payload = {"embeds": embeds}
    while True:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 1)
            time.sleep(float(retry_after) + 0.5)
            continue
        resp.raise_for_status()
        return


def chunked(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main():
    if not DRY_RUN and not DISCORD_WEBHOOK_URL:
        raise SystemExit("DISCORD_WEBHOOK_URL is not set (and DRY_RUN is not set)")

    listings = fetch_listings()
    seen = load_seen()
    first_run = seen is None

    eligible_rows = [row for row in listings if eligible(row)]

    if first_run:
        seen = {row["id"] for row in eligible_rows}
        save_seen(seen)
        print(f"First run: seeded {len(seen)} existing job(s), posted nothing.")
        return

    new_rows = [row for row in eligible_rows if row["id"] not in seen]
    new_rows.sort(key=lambda r: r.get("date_posted") or 0)

    if not new_rows:
        print("No new jobs.")
        return

    print(f"Found {len(new_rows)} new job(s).")

    for batch in chunked(new_rows, MAX_EMBEDS_PER_MESSAGE):
        if DRY_RUN:
            for row in batch:
                print(f"[DRY RUN] Would post: {row.get('company_name')} - {row.get('title')} ({row.get('url')})")
            for row in batch:
                seen.add(row["id"])
        else:
            embeds = [build_embed(row) for row in batch]
            try:
                post_to_discord(embeds)
            except requests.RequestException as e:
                print(f"Error posting batch, will retry next run: {e}", file=sys.stderr)
                continue
            for row in batch:
                seen.add(row["id"])
            time.sleep(2)
        save_seen(seen)


if __name__ == "__main__":
    main()
