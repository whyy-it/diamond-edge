# Diamond Edge — Odds Database & Bet Tracker (Pro)

Automated full-coverage odds archiver on a 20K requests/month budget. Every game, every prop, every bookmaker, 5 snapshots per day. Never pay for historical odds data again.

## What This Does

**Odds Collector** runs 5x daily via GitHub Actions:
- 6:00 AM ET — Opening lines (where the edge lives)
- 9:00 AM ET — Morning (after sharps move)
- 1:00 PM ET — Midday (pre-afternoon games)
- 5:00 PM ET — Evening (pre-night games)
- 7:30 PM ET — Closing lines (for backtest comparison)

**Data captured per snapshot:**
- Moneylines, spreads, and totals from **14 bookmakers**
- Alternate spreads and totals (FanDuel, DraftKings, BetMGM)
- **Player prop lines for EVERY game** — full market coverage:
  - MLB: hits, TB, HR, K, RBI, runs, walks, SB, pitcher hits/walks/ER
  - NHL: goals, assists, points, SOG, saves, blocked shots, PP points
  - NBA: points, rebounds, assists, threes, blocks, steals, turnovers, PRA, double-doubles
  - NFL: pass TDs/yds/completions/INTs, rush yds/attempts, rec yds/receptions, anytime TD, kicking
- Game scores and results for auto-grading

**Results Grader** runs daily at 4 AM ET:
- Fetches completed scores
- Auto-grades moneyline bets (W/L/P)
- Flags prop bets for manual grading
- Exports weekly CSV reports every Sunday

**Bet Tracker** — fully automatic:
- Every EV+ bet the model finds is auto-logged with timestamp, line, book, edge, Kelly stake, and projection source
- Grade results with W/L/P buttons after games finish
- Running P&L stats by sport, bet type, and projection source

---

## Quick Setup (5 minutes)

### 1. Upload files to your `diamond-edge` GitHub repo

Your repo should look like this:

```
diamond-edge/
├── index.html                  ← Diamond Edge v10 app
├── collector/
│   ├── collect_odds.py         ← odds fetcher (all games, all props)
│   ├── grade_bets.py           ← bet auto-grader + P&L stats
│   ├── export_data.py          ← JSON → CSV converter
│   └── requirements.txt
├── tracker/
│   └── bets.json               ← auto-tracked bet history
├── data/                       ← auto-populated by collector
│   └── .gitkeep
└── .github/
    └── workflows/
        ├── odds-collector.yml  ← 5x daily, full coverage
        └── results-grader.yml  ← daily grading + weekly export
```

### 2. Add your API key as a GitHub Secret

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `ODDS_API_KEY`
4. Value: your The Odds API key
5. Click **Add secret**

### 3. Enable GitHub Actions

1. Go to repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"** if prompted
3. You should see "Odds Collector" and "Results Grader" listed

### 4. Test it

1. **Actions** → **Odds Collector** → **Run workflow** → **Run**
2. Wait 2-5 minutes (it fetches props for every game)
3. Check the `data/` folder — you'll see JSON files appear

That's it. The cron jobs handle everything from here.

---

## API Budget (20,000/month)

| What | Per Day | Monthly |
|------|---------|---------|
| Game odds (4 sports × 5 snapshots) | 20 | 600 |
| Props (ALL events × 5 snapshots) | ~175 | ~5,250 |
| Alt lines (4 sports × 2/day) | 8 | 240 |
| Scores (4 sports × 2/day) | 8 | 240 |
| **Total** | **~211** | **~6,330** |
| **Remaining budget** | | **~13,670** |

You're using about 32% of your quota. Headroom for adding more sports, more snapshots, or manual re-pulls.

---

## Auto-Tracked Bet History

The Diamond Edge v10 app automatically logs every EV+ bet to browser localStorage the moment it appears on the Bets tab. No buttons to click — if the model finds an edge, it's recorded.

Each tracked bet includes: sport, player/team, market, line, book, edge (% or pp), Kelly stake, wager amount, projection source, and timestamp.

**Grading bets:** After games finish, use the W / L / P buttons next to each bet. The tracker instantly calculates P&L, ROI, and win rate.

**Syncing to GitHub for permanent storage:**
1. Open browser console (F12 → Console)
2. Run: `copy(JSON.stringify(JSON.parse(localStorage.getItem('de_bet_tracker'))))`
3. Paste into `tracker/bets.json` in the repo → commit
4. The Results Grader workflow auto-grades ML bets against archived scores

**P&L stats breakdown:** The grader shows results sliced by sport (MLB/NHL/NBA/NFL), bet type (ML/Prop), and projection source (statcast/poisson/model/consensus) — so you can see exactly which signal sources are profitable.

---

## Data Structure

```
data/
├── mlb/
│   ├── odds/
│   │   ├── 2026-03-27.json       ← array of 5 timestamped snapshots
│   │   ├── 2026-03-28.json
│   │   └── ...
│   ├── props/
│   │   ├── 2026-03-27.json       ← every player prop for every game
│   │   └── ...
│   ├── alt_lines/
│   │   ├── 2026-03-27.json       ← alternate spreads/totals
│   │   └── ...
│   ├── scores/
│   │   ├── 2026-03-27.json       ← game results
│   │   └── ...
│   └── ...
├── nhl/
│   └── (same structure)
├── nba/
│   └── (same structure)
├── nfl/
│   └── (same structure)
├── exports/
│   ├── mlb_game_lines_2026.csv   ← weekly auto-export
│   ├── mlb_props_2026.csv
│   ├── mlb_results_2026.csv
│   └── ...
└── summary.json
```

Each snapshot is labeled (opening/morning/midday/evening/closing) so you can isolate opening vs closing line movement for backtesting.

---

## Running Locally

```bash
export ODDS_API_KEY="your_key_here"

# Full collection (all sports, all props, all games)
python collector/collect_odds.py

# Single sport
python collector/collect_odds.py --sport nhl --snapshot manual

# Skip props to save quota
python collector/collect_odds.py --no-props

# Just scores
python collector/collect_odds.py --scores-only

# Grade bets
python collector/grade_bets.py

# P&L stats
python collector/grade_bets.py --stats

# Export closing lines to CSV
python collector/export_data.py --closing-only

# Export everything
python collector/export_data.py
```

---

## What You'll Have After One Season

By October 2026, your database will contain:
- **Opening + closing lines** for every MLB, NHL, NBA, and NFL game
- **5 daily snapshots** showing exactly how lines moved and when
- **Every player prop line** from 14 bookmakers across all markets
- **Alternate spreads and totals** from the big 3 books
- **Complete game results** with final scores
- **Full bet history** with auto-tracked P&L by source

That's more granular than Odds Warehouse (they only have closing lines, no props, no movement). And it's free — you already have the API plan.
