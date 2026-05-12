# Bahamas Election Tracker — Deploy Guide

This setup **reuses your existing Firebase and Render accounts** from the WV tracker. The Bahamas data lives in a separate Firebase node so it doesn't conflict with WV.

**Total deploy time: ~10 minutes.**

## Data source

The scraper pulls from **The Nassau Guardian's live election results page**:
https://www.thenassauguardian.com/news/politics/election-results/

That page is built on the BLOX/TownNews "electionsstats" platform, which:
- Updates automatically as the Guardian's election desk calls constituencies
- Has clean per-constituency HTML tables (one table per race)
- Shows live "(X%) precincts reporting · Updated Y min ago" status per constituency

The scraper handles minor name differences automatically (e.g. "Bains Town" → "Bain Town", "Bimini and The Berry Islands" → "Bimini and Berry Islands").

## Step 1 — Upload to GitHub

1. Go to https://github.com/new
2. Repo name: `bahamas-tracker`. Public. Create.
3. "Uploading an existing file" → drag in `scraper.py`, `requirements.txt`, `dashboard.html`
4. Commit

## Step 2 — Deploy the scraper on Render

1. Go to https://dashboard.render.com
2. Click **+ New** → **Background Worker**
3. Connect repo `bahamas-tracker`
4. Settings:
   - **Name:** `bahamas-tracker-scraper`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python scraper.py --loop`
   - **Instance Type:** Free
5. **Environment Variables:**
   - `FIREBASE_URL` = `https://wv-tracker-default-rtdb.firebaseio.com` (same as your WV tracker)
   - `FIREBASE_NODE` = `bahamas_live` (isolates Bahamas data from WV data)
   - `POLL_SECONDS` = `180`
6. Click **Create Background Worker**.

Wait ~2 min. Look at the logs. **Even right now (before polls close)** you should see something like:

```
=== run @ 2026-05-12T... ===
[fetch] https://www.thenassauguardian.com/news/politics/election-results/
[parse] found 41 constituency tables
[match] 41/41 constituencies matched, 0 with votes
[firebase] pushed OK · PLP 0 FNM 0 COI 0 IND 0 (reporting 0/41)
```

If you see `41/41 matched` — perfect, you're ready. Counts stay at 0 until results come in.

If you see fewer than 41 matched, the logs will print which ones missed and what scraped names came in. Send me the log and I'll patch the matcher.

## Step 3 — Host the dashboard

Same as WV — drag `dashboard.html` onto https://app.netlify.com/drop

1. Get a random URL → optionally rename to `sw2-bahamas-2026` or similar in Netlify
2. Send that URL to your clients

## What clients see

The dashboard shows three things, top to bottom:

1. **Seat tally header** — PLP / FNM / COI / Independent seat counts, big and obvious. Includes a "leads with X (Y to majority)" status line that flips to "🏆 PLP/FNM wins majority" when one party crosses 21.
2. **Filter buttons** — All / Reporting / PLP-led / FNM-led / COI-led / Indep-led
3. **41 constituency cards** — each showing PLP/FNM/COI candidates + any independents, vote totals, percentages, and a "X LEADS" badge on the current winner

The page is read-only — clients can't enter or change anything. Your scraper writes; their dashboards read.

## Timing tonight

- **5 PM AST (4 PM ET):** Final hour of voting. Cards show 0s.
- **6 PM AST (5 PM ET):** Polls close.
- **6:30-7:30 PM AST:** Family Islands (small electorates) report first.
- **8-10 PM AST:** New Providence and Grand Bahama fill in. The PM race is usually decided in this window.
- **By 11 PM AST:** Election typically conceded if a majority is clear.

The scraper polls the Guardian every 3 minutes the whole night. No babysitting needed.

## If something looks wrong

- **Cards showing 0 votes for races already called by news outlets:** The Nassau Guardian's update cadence may lag. Check the page directly — if numbers are there, the parser may need a tweak. Send me a Render log snippet.
- **Specific constituency not matching:** Check Render logs for the `missing:` line; tell me which one and I'll patch the matcher.
- **Connection error on the dashboard:** Firebase URL mismatch between scraper and dashboard. Both should be the same `wv-tracker-default-rtdb.firebaseio.com` URL but the dashboard reads from `bahamas_live` node while WV reads from `live`.

## Cost recap

Same as WV — everything free.
- Render: 2 background workers, both on free tier
- Firebase: shared database, separate data node
- Netlify: separate site for Bahamas
