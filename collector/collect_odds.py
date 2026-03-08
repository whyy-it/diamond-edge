#!/usr/bin/env python3
"""
Diamond Edge — Odds Collector (Pro — 20K/month)
Full-coverage odds archiver: every game, every prop, every bookmaker.

Budget: 20,000 requests/month
Schedule: 5x daily (open, morning, midday, evening, close)
Coverage: MLB, NHL, NBA, NFL — ALL events, ALL prop markets

Estimated usage (~12K/month):
  Game odds:  4 sports × 5/day × 30             =   600
  Props:      ~35 events/day × 5 snaps × 30     = 5,250
  Scores:     4 sports × 2/day × 30             =   240
  Alt lines:  4 sports × 2/day × 30             =   240
  Headroom:                                      ~5,670

Usage:
  python collect_odds.py                          # All active sports
  python collect_odds.py --sport mlb              # Single sport
  python collect_odds.py --scores-only            # Just results
  python collect_odds.py --snapshot opening        # Tag snapshot
"""

import os, sys, json, argparse, time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: pip install requests"); sys.exit(1)

API_KEY = os.environ.get("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4/sports"
DATA_DIR = Path(__file__).parent.parent / "data"

SPORTS = {
    "mlb": {
        "key": "baseball_mlb",
        "prop_markets": ",".join([
            "batter_hits","batter_total_bases","batter_home_runs",
            "pitcher_strikeouts","batter_rbis","batter_runs_scored",
            "batter_walks","batter_stolen_bases","pitcher_hits_allowed",
            "pitcher_walks","pitcher_earned_runs",
        ]),
        "alt_markets": "alternate_spreads,alternate_totals",
    },
    "nhl": {
        "key": "icehockey_nhl",
        "prop_markets": ",".join([
            "player_goals","player_assists","player_points",
            "player_shots_on_goal","player_saves",
            "player_blocked_shots","player_power_play_points",
        ]),
        "alt_markets": "alternate_spreads,alternate_totals",
    },
    "nba": {
        "key": "basketball_nba",
        "prop_markets": ",".join([
            "player_points","player_rebounds","player_assists",
            "player_threes","player_blocks","player_steals",
            "player_turnovers","player_points_rebounds_assists",
            "player_double_double",
        ]),
        "alt_markets": "alternate_spreads,alternate_totals",
    },
    "nfl": {
        "key": "americanfootball_nfl",
        "prop_markets": ",".join([
            "player_pass_tds","player_pass_yds","player_pass_completions",
            "player_pass_interceptions","player_rush_yds","player_rush_attempts",
            "player_reception_yds","player_receptions","player_anytime_td",
            "player_kicking_points",
        ]),
        "alt_markets": "alternate_spreads,alternate_totals",
    },
}

# All US bookmakers — PA-licensed plus major offshore for line comparison
BOOKMAKERS = [
    "fanduel","draftkings","betmgm","williamhill_us",
    "betrivers","fanatics","betparx","espnbet",
    "pointsbetus","bovada","betonlineag","mybookieag",
    "lowvig","betus",
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def api_get(endpoint, params=None):
    if not API_KEY:
        log("ERROR: ODDS_API_KEY not set"); sys.exit(1)
    url = f"{BASE_URL}/{endpoint}"
    p = {"apiKey": API_KEY}
    if params: p.update(params)
    for attempt in range(3):
        try:
            resp = requests.get(url, params=p, timeout=30)
            remaining = resp.headers.get("x-requests-remaining", "?")
            used = resp.headers.get("x-requests-used", "?")
            if resp.status_code == 429:
                log(f"  Rate limited — waiting 10s ({attempt+1}/3)")
                time.sleep(10); continue
            if resp.status_code != 200:
                log(f"  API error {resp.status_code}: {resp.text[:200]}")
                return None, remaining
            log(f"  ✓ quota: {remaining} remaining ({used} used)")
            return resp.json(), remaining
        except requests.exceptions.Timeout:
            log(f"  Timeout ({attempt+1}/3)"); time.sleep(2)
        except Exception as e:
            log(f"  Error: {e}"); return None, "?"
    return None, "?"

def collect_game_odds(sport_key):
    log(f"  Game odds...")
    data, rem = api_get(f"{sport_key}/odds/", {
        "regions": "us,us2", "markets": "h2h,spreads,totals",
        "oddsFormat": "american", "bookmakers": ",".join(BOOKMAKERS),
    })
    if data: log(f"    → {len(data)} events")
    return data, rem

def collect_alt_lines(sport_key):
    log(f"  Alt lines...")
    data, rem = api_get(f"{sport_key}/odds/", {
        "regions": "us", "markets": "alternate_spreads,alternate_totals",
        "oddsFormat": "american", "bookmakers": "fanduel,draftkings,betmgm",
    })
    if data: log(f"    → {len(data)} events")
    return data, rem

def collect_all_props(sport_key, event_ids, markets):
    results = []
    log(f"  Props for ALL {len(event_ids)} events...")
    for i, eid in enumerate(event_ids):
        data, rem = api_get(f"{sport_key}/events/{eid}/odds", {
            "regions": "us", "markets": markets,
            "oddsFormat": "american", "bookmakers": ",".join(BOOKMAKERS),
        })
        if data and data.get("bookmakers"):
            results.append(data)
        if (i+1) % 5 == 0 or i == len(event_ids)-1:
            log(f"    → {i+1}/{len(event_ids)} done ({len(results)} with data)")
        time.sleep(0.2)
    return results

def collect_scores(sport_key, days_back=3):
    log(f"  Scores (last {days_back} days)...")
    data, rem = api_get(f"{sport_key}/scores/", {"daysFrom": days_back})
    if data:
        completed = sum(1 for g in data if g.get("completed"))
        log(f"    → {completed} completed / {len(data)} total")
    return data, rem

def save_snapshot(sport, data_type, data, label=""):
    now = datetime.now(timezone.utc)
    out_dir = DATA_DIR / sport / data_type
    out_dir.mkdir(parents=True, exist_ok=True)
    filepath = out_dir / f"{now.strftime('%Y-%m-%d')}.json"
    existing = []
    if filepath.exists():
        try: existing = json.loads(filepath.read_text())
        except: existing = []
    existing.append({
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": label, "sport": sport, "snapshot_type": data_type,
        "event_count": len(data) if isinstance(data, list) else 1,
        "data": data,
    })
    filepath.write_text(json.dumps(existing, indent=2))
    log(f"    Saved → {filepath.name} ({len(existing)} snapshots today)")

def run_collection(sport_name, skip_props=False, skip_alt=False, label="", scores_days=3):
    cfg = SPORTS.get(sport_name)
    if not cfg: log(f"Unknown sport: {sport_name}"); return
    sport_key = cfg["key"]
    log(f"\n{'═'*55}")
    log(f"  {sport_name.upper()} — full collection")
    log(f"{'═'*55}")

    odds_data, rem = collect_game_odds(sport_key)
    if odds_data:
        save_snapshot(sport_name, "odds", odds_data, label)
        if not skip_props:
            event_ids = [e["id"] for e in odds_data]
            props_data = collect_all_props(sport_key, event_ids, cfg["prop_markets"])
            if props_data:
                save_snapshot(sport_name, "props", props_data, label)
        if not skip_alt:
            alt_data, _ = collect_alt_lines(sport_key)
            if alt_data:
                save_snapshot(sport_name, "alt_lines", alt_data, label)

    scores_data, _ = collect_scores(sport_key, scores_days)
    if scores_data:
        save_snapshot(sport_name, "scores", scores_data, label)
    log(f"  {sport_name.upper()} done — API remaining: {rem}")

def generate_summary():
    summary = {"generated": datetime.now(timezone.utc).isoformat(), "sports": {}}
    for sport in SPORTS:
        sport_dir = DATA_DIR / sport
        if not sport_dir.exists(): continue
        ss = {}
        for dtype in ["odds","props","scores","alt_lines"]:
            dd = sport_dir / dtype
            if not dd.exists(): continue
            files = sorted(dd.glob("*.json"))
            if not files: continue
            total_snaps = 0; total_ev = 0
            for f in files:
                try:
                    d = json.loads(f.read_text())
                    total_snaps += len(d) if isinstance(d, list) else 1
                    for snap in (d if isinstance(d, list) else [d]):
                        total_ev += snap.get("event_count", 0)
                except: pass
            ss[dtype] = {"days":len(files),"snapshots":total_snaps,"events":total_ev,"first":files[0].stem,"last":files[-1].stem}
        if ss: summary["sports"][sport] = ss
    p = DATA_DIR / "summary.json"
    p.write_text(json.dumps(summary, indent=2))
    log(f"\nSummary → {p}")
    return summary

def detect_active():
    m = datetime.now().month
    active = []
    if 3 <= m <= 11: active.append("mlb")
    if m >= 10 or m <= 6: active.append("nhl")
    if m >= 10 or m <= 6: active.append("nba")
    if m >= 8 or m <= 2: active.append("nfl")
    return active or list(SPORTS.keys())

def main():
    parser = argparse.ArgumentParser(description="Diamond Edge Odds Collector (Pro)")
    parser.add_argument("--sport", choices=list(SPORTS.keys())+["all"], default="all")
    parser.add_argument("--no-props", action="store_true")
    parser.add_argument("--no-alt", action="store_true")
    parser.add_argument("--scores-only", action="store_true")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--scores-days", type=int, default=3)
    args = parser.parse_args()

    log("Diamond Edge Odds Collector (Pro — 20K/month)")
    log(f"API key: {'***'+API_KEY[-4:] if API_KEY else 'NOT SET'}")
    if not API_KEY: log("ERROR: Set ODDS_API_KEY"); sys.exit(1)

    active = [args.sport] if args.sport != "all" else detect_active()
    log(f"Sports: {', '.join(s.upper() for s in active)}")

    for sport in active:
        if args.scores_only:
            cfg = SPORTS[sport]
            sd, _ = collect_scores(cfg["key"], args.scores_days)
            if sd: save_snapshot(sport, "scores", sd, args.snapshot)
        else:
            run_collection(sport, args.no_props, args.no_alt, args.snapshot, args.scores_days)

    generate_summary()
    log("\nDone!")

if __name__ == "__main__":
    main()
