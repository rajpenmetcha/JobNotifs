# SimplifyJobs New-Grad Discord Notifier

Polls the public `listings.json` behind [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions)
every 30 minutes via a scheduled GitHub Action, and posts one Discord embed per
newly-added job. No server, no fork, no database — state is a single
`seen_ids.json` file committed back to this repo each run.

## Setup

1. **Create the repo.** Push these files to a new (empty) GitHub repo.

2. **Create a Discord webhook.**
   In Discord: the target channel → gear icon (Edit Channel) → **Integrations**
   → **Webhooks** → **New Webhook** → give it a name → **Copy Webhook URL**.

3. **Add the webhook URL as a repo secret.**
   In GitHub: repo → **Settings** → **Secrets and variables** → **Actions**
   → **New repository secret** → name it `DISCORD_WEBHOOK_URL`, paste the
   webhook URL → **Add secret**.

4. **Enable Actions.**
   Repo → **Actions** tab → if prompted, click to enable workflows for the repo.

That's it. The workflow runs every 30 minutes on its own. On its very first
run it will seed `seen_ids.json` with every currently-active job and post
nothing (this avoids dumping the entire backlog into Discord). From then on,
only newly-added jobs get posted.

## Testing manually

Repo → **Actions** tab → **Notify new jobs** workflow → **Run workflow**.

- Leave `dry_run` as `false` for a real run (posts to Discord if there are new jobs).
- Set `dry_run` to `true` to print what *would* be posted to the Action logs
  without calling Discord at all, and without needing a real webhook secret.

## Testing locally

```bash
pip install -r requirements.txt

# First run: seeds seen_ids.json, posts nothing.
python notifier.py

# Simulate a "new job": remove one id from seen_ids.json, then re-run.
# With DRY_RUN set, it just prints what it would post:
DRY_RUN=1 python notifier.py

# Real post to your webhook:
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python notifier.py
```

## Changing the schedule or filters

- **Cron schedule:** edit the `cron:` line in `.github/workflows/notify.yml`
  (currently `*/30 * * * *`, every 30 minutes). GitHub's scheduler is
  best-effort and can run a few minutes late, especially on the hour.
- **Keyword filter:** edit `TITLE_KEYWORDS` at the top of `notifier.py`
  (e.g. `["software engineer", "backend"]`) to only post matching titles.
  Empty list (default) posts everything.

## How it works

1. Fetch `listings.json` from the `dev` branch of `SimplifyJobs/New-Grad-Positions`
   (retries once on network failure, then fails the run loudly).
2. Filter to rows where `active` and `is_visible` are both true.
3. Diff against `seen_ids.json` (keyed by each job's stable `id`) to find new rows.
4. Post each new row as a Discord embed (title links to the apply URL; fields
   for Company, Location, Sponsorship, Date Posted), batched at 10 embeds per
   message with a short delay between messages, honoring Discord's 429
   rate-limit responses.
5. A job's id is only added to `seen_ids.json` after it's successfully posted
   (or printed, in dry-run mode) — so a failed post retries on the next run
   instead of being silently dropped.
6. The workflow commits `seen_ids.json` back to the repo if it changed.
