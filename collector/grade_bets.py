#!/usr/bin/env python3
"""
Diamond Edge — Bet Grader
Auto-grades tracked bets against archived game scores.
Works with bets auto-tracked by the v10 app.

Usage:
  python grade_bets.py                    # Grade all pending bets
  python grade_bets.py --dry-run          # Preview
  python grade_bets.py --stats            # Show P&L
  python grade_bets.py --export-csv       # Export history to CSV
"""

import os, sys, json, csv, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRACKER_DIR = Path(__file__).parent.parent / "tracker"
TRACKER_FILE = TRACKER_DIR / "bets.json"
HISTORY_FILE = TRACKER_DIR / "history.csv"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_bets():
    if not TRACKER_FILE.exists(): return []
    try: return json.loads(TRACKER_FILE.read_text())
    except: return []

def save_bets(bets):
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    TRACKER_FILE.write_text(json.dumps(bets, indent=2))

def load_scores(sport, date_str):
    scores_dir = DATA_DIR / sport / "scores"
    for offset in [0, -1, 1]:
        dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=offset)
        f = scores_dir / f"{dt.strftime('%Y-%m-%d')}.json"
        if f.exists():
            try:
                snaps = json.loads(f.read_text())
                if snaps and isinstance(snaps, list):
                    return snaps[-1].get("data", [])
            except: pass
    return []

def find_game(scores, matchup):
    parts = matchup.split(" @ ")
    if len(parts) != 2: return None
    away, home = parts[0].strip(), parts[1].strip()
    for g in scores:
        if not g.get("completed"): continue
        gh, ga = g.get("home_team",""), g.get("away_team","")
        if (home in gh or gh in home) and (away in ga or ga in away):
            return g
    return None

def grade_ml(bet, game):
    scores = game.get("scores", [])
    if not scores or len(scores) < 2: return None
    hs = as_ = 0
    for s in scores:
        if s.get("name") == game.get("home_team"): hs = int(s.get("score",0))
        elif s.get("name") == game.get("away_team"): as_ = int(s.get("score",0))
    if hs == as_: return "P"
    winner = game["home_team"] if hs > as_ else game["away_team"]
    bt = bet.get("player","")
    return "W" if (bt in winner or winner in bt) else "L"

def calc_payout(bet, result):
    amt = bet.get("amount", 0)
    try: ml = int(str(bet.get("line","0")).replace("+",""))
    except: return 0
    if result == "W":
        return round(amt * (ml/100), 2) if ml > 0 else round(amt * (100/(-ml)), 2) if ml < 0 else 0
    elif result == "L": return -amt
    return 0

def grade_all(dry_run=False):
    bets = load_bets()
    pending = [b for b in bets if b.get("result") is None]
    if not pending: log("No pending bets."); return bets

    log(f"Grading {len(pending)} pending bets...")
    graded = manual = 0

    for bet in pending:
        sport = bet.get("sport","mlb")
        matchup = bet.get("matchup","")
        gt = bet.get("time","")
        if gt:
            try: date_str = datetime.fromisoformat(gt.replace("Z","+00:00")).strftime("%Y-%m-%d")
            except: continue
        else: continue

        scores = load_scores(sport, date_str)
        if not scores: continue

        game = find_game(scores, matchup)
        if not game: continue

        result = grade_ml(bet, game) if bet.get("type") == "ML" else None
        if result:
            bet["result"] = result
            bet["payout"] = calc_payout(bet, result)
            bet["graded_at"] = datetime.now(timezone.utc).isoformat()
            graded += 1
            log(f"  ✓ {bet.get('player')} — {result} (${bet['payout']:+.2f})")
        else:
            manual += 1

    log(f"Graded: {graded}, Manual needed: {manual}")
    if not dry_run and graded > 0:
        save_bets(bets)
        log(f"Saved {len(bets)} bets")
    return bets

def stats(bets):
    gr = [b for b in bets if b.get("result")]
    if not gr: return None
    w = sum(1 for b in gr if b["result"]=="W")
    l = sum(1 for b in gr if b["result"]=="L")
    p = sum(1 for b in gr if b["result"]=="P")
    pend = sum(1 for b in bets if not b.get("result"))
    wag = sum(b.get("amount",0) for b in gr)
    pay = sum(b.get("payout",0) for b in gr)
    roi = (pay/wag*100) if wag > 0 else 0

    by_sport = {}
    for b in gr:
        s = b.get("sport","?")
        if s not in by_sport: by_sport[s] = {"W":0,"L":0,"P":0,"wag":0,"pay":0}
        by_sport[s][b["result"]] += 1
        by_sport[s]["wag"] += b.get("amount",0)
        by_sport[s]["pay"] += b.get("payout",0)

    by_type = {}
    for b in gr:
        t = b.get("type","?")
        if t not in by_type: by_type[t] = {"W":0,"L":0,"P":0,"wag":0,"pay":0}
        by_type[t][b["result"]] += 1
        by_type[t]["wag"] += b.get("amount",0)
        by_type[t]["pay"] += b.get("payout",0)

    by_source = {}
    for b in gr:
        src = b.get("projSource","?")
        if src not in by_source: by_source[src] = {"W":0,"L":0,"P":0,"wag":0,"pay":0}
        by_source[src][b["result"]] += 1
        by_source[src]["wag"] += b.get("amount",0)
        by_source[src]["pay"] += b.get("payout",0)

    return {"total":len(gr),"pending":pend,"record":f"{w}-{l}-{p}",
            "win_rate":f"{w/len(gr)*100:.1f}%","wagered":round(wag,2),
            "profit":round(pay,2),"roi":f"{roi:+.1f}%",
            "by_sport":by_sport,"by_type":by_type,"by_source":by_source}

def export_csv(bets):
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date","Sport","Type","Player","Market","Line","Book",
                     "Edge","EdgeUnit","Kelly%","Wager","Result","Payout",
                     "Source","HighVar","PaperTrade","Matchup","AutoTracked"])
        for b in sorted(bets, key=lambda x: x.get("time","")):
            dt = ""
            if b.get("time"):
                try: dt = datetime.fromisoformat(b["time"].replace("Z","+00:00")).strftime("%Y-%m-%d")
                except: pass
            w.writerow([dt, b.get("sport",""), b.get("type",""), b.get("player",""),
                        b.get("market",""), b.get("line",""), b.get("book",""),
                        b.get("edge",""), b.get("edgeUnit",""), b.get("kelly",""),
                        b.get("amount",0), b.get("result","PENDING"),
                        b.get("payout","") if b.get("result") else "",
                        b.get("projSource",""), b.get("highVar",False),
                        b.get("paperTrade",False), b.get("matchup",""),
                        b.get("autoTracked",False)])
    log(f"Exported {len(bets)} bets → {HISTORY_FILE}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--export-csv", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    bets = load_bets()
    log(f"Loaded {len(bets)} tracked bets")

    if args.stats:
        s = stats(bets)
        if s:
            log(f"\n{'='*45}")
            log(f"  DIAMOND EDGE — BET TRACKER")
            log(f"{'='*45}")
            log(f"  Record:   {s['record']}  ({s['win_rate']})")
            log(f"  Wagered:  ${s['wagered']:.2f}")
            log(f"  Profit:   ${s['profit']:+.2f}")
            log(f"  ROI:      {s['roi']}")
            log(f"  Pending:  {s['pending']}")
            for k,v in s["by_sport"].items():
                r = (v["pay"]/v["wag"]*100) if v["wag"]>0 else 0
                log(f"  {k.upper()}: {v['W']}-{v['L']}-{v['P']}  ${v['pay']:+.2f}  ({r:+.1f}%)")
            for k,v in s["by_type"].items():
                r = (v["pay"]/v["wag"]*100) if v["wag"]>0 else 0
                log(f"  {k}: {v['W']}-{v['L']}-{v['P']}  ${v['pay']:+.2f}  ({r:+.1f}%)")
            log(f"\n  By projection source:")
            for k,v in s["by_source"].items():
                r = (v["pay"]/v["wag"]*100) if v["wag"]>0 else 0
                log(f"  {k}: {v['W']}-{v['L']}-{v['P']}  ${v['pay']:+.2f}  ({r:+.1f}%)")
        else: log("No graded bets yet.")
        return

    if args.export_csv: export_csv(bets); return

    graded = grade_all(args.dry_run)
    s = stats(graded)
    if s: log(f"\nRecord: {s['record']} | ROI: {s['roi']} | Profit: ${s['profit']:+.2f}")

if __name__ == "__main__":
    main()
