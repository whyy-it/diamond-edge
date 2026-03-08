#!/usr/bin/env python3
"""
Diamond Edge — Data Exporter
Converts archived JSON snapshots to clean CSVs for backtesting.

Usage:
  python export_data.py                   # Export everything
  python export_data.py --sport mlb       # Single sport
  python export_data.py --closing-only    # Last snapshot per day only
"""

import json, csv, argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"
EXPORT_DIR = DATA_DIR / "exports"

BOOKMAKERS = [
    "fanduel","draftkings","betmgm","williamhill_us",
    "betrivers","fanatics","betparx","espnbet",
    "pointsbetus","bovada","betonlineag","mybookieag",
    "lowvig","betus",
]
BK_LABELS = {
    "fanduel":"FanDuel","draftkings":"DraftKings","betmgm":"BetMGM",
    "williamhill_us":"Caesars","betrivers":"BetRivers","fanatics":"Fanatics",
    "betparx":"betPARX","espnbet":"theScore","pointsbetus":"PointsBet",
    "bovada":"Bovada","betonlineag":"BetOnline","mybookieag":"MyBookie",
    "lowvig":"LowVig","betus":"BetUS",
}

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def export_game_odds(sport, closing_only=False):
    odds_dir = DATA_DIR / sport / "odds"
    if not odds_dir.exists(): return
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(odds_dir.glob("*.json"))
    if not files: return

    year = files[-1].stem[:4]
    out = EXPORT_DIR / f"{sport}_game_lines_{year}.csv"

    header = ["snapshot_time","snapshot_label","game_date","commence_time",
              "event_id","home_team","away_team"]
    for bk in BOOKMAKERS:
        lb = BK_LABELS.get(bk,bk)
        header += [f"{lb}_home_ml",f"{lb}_away_ml",
                   f"{lb}_home_spread",f"{lb}_home_spread_odds",
                   f"{lb}_total",f"{lb}_over_odds",f"{lb}_under_odds"]
    header += ["consensus_home_ml","consensus_away_ml","consensus_total","book_count"]

    rows = []
    for f in files:
        try: snaps = json.loads(f.read_text())
        except: continue
        proc = [snaps[-1]] if closing_only and snaps else snaps
        for snap in proc:
            ts = snap.get("timestamp","")
            label = snap.get("label","")
            for ev in snap.get("data",[]):
                row = {"snapshot_time":ts,"snapshot_label":label,"game_date":f.stem,
                       "commence_time":ev.get("commence_time",""),
                       "event_id":ev.get("id",""),
                       "home_team":ev.get("home_team",""),
                       "away_team":ev.get("away_team","")}
                hmls,amls,tots = [],[],[]
                bk_count = 0
                for bm in ev.get("bookmakers",[]):
                    bk = bm.get("key","")
                    if bk not in BOOKMAKERS: continue
                    lb = BK_LABELS.get(bk,bk)
                    bk_count += 1
                    for mkt in bm.get("markets",[]):
                        if mkt["key"]=="h2h":
                            for o in mkt.get("outcomes",[]):
                                if o["name"]==ev["home_team"]: row[f"{lb}_home_ml"]=o.get("price"); hmls.append(o["price"])
                                elif o["name"]==ev["away_team"]: row[f"{lb}_away_ml"]=o.get("price"); amls.append(o["price"])
                        elif mkt["key"]=="spreads":
                            for o in mkt.get("outcomes",[]):
                                if o["name"]==ev["home_team"]: row[f"{lb}_home_spread"]=o.get("point"); row[f"{lb}_home_spread_odds"]=o.get("price")
                        elif mkt["key"]=="totals":
                            for o in mkt.get("outcomes",[]):
                                if o["name"]=="Over": row[f"{lb}_total"]=o.get("point"); row[f"{lb}_over_odds"]=o.get("price"); tots.append(o.get("point",0))
                                elif o["name"]=="Under": row[f"{lb}_under_odds"]=o.get("price")
                if hmls: row["consensus_home_ml"]=round(sum(hmls)/len(hmls))
                if amls: row["consensus_away_ml"]=round(sum(amls)/len(amls))
                ut = [t for t in set(tots) if t>0]
                if ut: row["consensus_total"]=round(sum(ut)/len(ut),1)
                row["book_count"]=bk_count
                rows.append(row)

    with open(out,"w",newline="") as cf:
        w = csv.DictWriter(cf, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)
    log(f"  {len(rows)} game lines → {out.name}")

def export_props(sport):
    props_dir = DATA_DIR / sport / "props"
    if not props_dir.exists(): return
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(props_dir.glob("*.json"))
    if not files: return

    year = files[-1].stem[:4]
    out = EXPORT_DIR / f"{sport}_props_{year}.csv"
    header = ["snapshot_time","snapshot_label","game_date","event_id",
              "home_team","away_team","market","player","line",
              "over_odds","under_odds","book"]
    rows = []
    for f in files:
        try: snaps = json.loads(f.read_text())
        except: continue
        for snap in snaps:
            ts = snap.get("timestamp","")
            label = snap.get("label","")
            for ev in snap.get("data",[]):
                eid = ev.get("id","")
                home = ev.get("home_team","")
                away = ev.get("away_team","")
                for bm in ev.get("bookmakers",[]):
                    bl = BK_LABELS.get(bm.get("key",""),bm.get("key",""))
                    for mkt in bm.get("markets",[]):
                        bp = defaultdict(dict)
                        for o in mkt.get("outcomes",[]):
                            nm = o.get("description",o.get("name",""))
                            bp[nm]["line"] = o.get("point")
                            if o.get("name")=="Over": bp[nm]["over"]=o.get("price")
                            elif o.get("name")=="Under": bp[nm]["under"]=o.get("price")
                        for pl,d in bp.items():
                            rows.append({"snapshot_time":ts,"snapshot_label":label,
                                "game_date":f.stem,"event_id":eid,"home_team":home,
                                "away_team":away,"market":mkt.get("key",""),
                                "player":pl,"line":d.get("line"),
                                "over_odds":d.get("over"),"under_odds":d.get("under"),"book":bl})

    with open(out,"w",newline="") as cf:
        w = csv.DictWriter(cf, fieldnames=header)
        w.writeheader()
        for r in rows: w.writerow(r)
    log(f"  {len(rows)} prop lines → {out.name}")

def export_scores(sport):
    sd = DATA_DIR / sport / "scores"
    if not sd.exists(): return
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(sd.glob("*.json"))
    if not files: return
    year = files[-1].stem[:4]
    out = EXPORT_DIR / f"{sport}_results_{year}.csv"
    header = ["game_date","event_id","commence_time","home_team","away_team",
              "home_score","away_score","completed"]
    seen = set(); rows = []
    for f in files:
        try: snaps = json.loads(f.read_text())
        except: continue
        for snap in snaps:
            for g in snap.get("data",[]):
                eid = g.get("id","")
                if eid in seen or not g.get("completed"): continue
                seen.add(eid)
                hs = as_ = ""
                for s in g.get("scores",[]):
                    if s.get("name")==g.get("home_team"): hs=s.get("score","")
                    elif s.get("name")==g.get("away_team"): as_=s.get("score","")
                rows.append({"game_date":f.stem,"event_id":eid,
                    "commence_time":g.get("commence_time",""),
                    "home_team":g.get("home_team",""),"away_team":g.get("away_team",""),
                    "home_score":hs,"away_score":as_,"completed":True})
    with open(out,"w",newline="") as cf:
        w = csv.DictWriter(cf, fieldnames=header)
        w.writeheader()
        for r in rows: w.writerow(r)
    log(f"  {len(rows)} results → {out.name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", default="all")
    parser.add_argument("--closing-only", action="store_true")
    args = parser.parse_args()
    log("Diamond Edge Data Exporter")
    sports = ["mlb","nhl","nba","nfl"] if args.sport=="all" else [args.sport]
    for s in sports:
        if not (DATA_DIR/s).exists(): continue
        log(f"\n{s.upper()}:")
        export_game_odds(s, args.closing_only)
        export_props(s)
        export_scores(s)
    log("\nDone!")

if __name__ == "__main__":
    main()
