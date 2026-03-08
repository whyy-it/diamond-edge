#!/usr/bin/env python3
"""
Diamond Edge — App Builder
Reads your local data files + current index.html, embeds the v11b model with
real team stats and pitcher Statcast data, removes props, outputs a ready-to-deploy app.

Usage:
  cd ~/Desktop/diamond-edge
  python3 build_v11b_app.py

Outputs: index.html (updated with v11b model)
"""

import os, csv, json, re
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~/Desktop/diamond_edge_pipeline/data"))
APP_DIR = Path(os.path.expanduser("~/Desktop/diamond-edge"))
MODEL_PATH = DATA_DIR / "v11b_model.json"

def load_model():
    with open(MODEL_PATH) as f:
        return json.load(f)

# Map FanGraphs abbreviations to full Odds API names
ABBREV_TO_FULL = {
    "ARI":"Arizona Diamondbacks","ATL":"Atlanta Braves","BAL":"Baltimore Orioles",
    "BOS":"Boston Red Sox","CHC":"Chicago Cubs","CHW":"Chicago White Sox",
    "CIN":"Cincinnati Reds","CLE":"Cleveland Guardians","COL":"Colorado Rockies",
    "DET":"Detroit Tigers","HOU":"Houston Astros","KC":"Kansas City Royals",
    "LAA":"Los Angeles Angels","LAD":"Los Angeles Dodgers","MIA":"Miami Marlins",
    "MIL":"Milwaukee Brewers","MIN":"Minnesota Twins","NYM":"New York Mets",
    "NYY":"New York Yankees","OAK":"Oakland Athletics","PHI":"Philadelphia Phillies",
    "PIT":"Pittsburgh Pirates","SD":"San Diego Padres","SEA":"Seattle Mariners",
    "SF":"San Francisco Giants","STL":"St. Louis Cardinals","TB":"Tampa Bay Rays",
    "TEX":"Texas Rangers","TOR":"Toronto Blue Jays","WSH":"Washington Nationals",
}

def full_name(abbr):
    return ABBREV_TO_FULL.get(abbr.strip(), abbr.strip())

def load_team_batting_2025():
    """Load 2025 team batting from FanGraphs."""
    path = DATA_DIR / "team_batting_2025.csv"
    teams = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            team = row.get("Team", "").strip()
            if not team: continue
            try:
                teams[team] = {
                    "wRC": float(row.get("wRC+", 100)),
                    "OPS": float(row.get("OPS", 0.720)),
                    "xwOBA": float(row.get("xwOBA", 0.320)),
                    "Barrel": float(row.get("Barrel%", 0.07)),
                    "EV": float(row.get("EV", 88.5)),
                    "BB": float(row.get("BB%", 0.08)),
                }
            except: continue
    print(f"  Team batting: {len(teams)} teams")
    return teams

def load_team_pitching_2025():
    path = DATA_DIR / "team_pitching_2025.csv"
    teams = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            team = row.get("Team", "").strip()
            if not team: continue
            try:
                teams[team] = {
                    "ERA": float(row.get("ERA", 4.00)),
                    "FIP": float(row.get("FIP", 4.00)),
                    "BB9": float(row.get("BB/9", 3.2)),
                    "xwOBA": float(row.get("xwOBA", 0.320)),
                }
            except: continue
    print(f"  Team pitching: {len(teams)} teams")
    return teams

def load_pitcher_xstats_2025():
    """Load top pitchers from 2025 Statcast (starters with 100+ PA)."""
    path = DATA_DIR / "pitcher_xstats_2025.csv"
    pitchers = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                pa = int(row.get("pa", 0))
                if pa < 100: continue  # Only real starters
                name_raw = row.get("last_name, first_name", "")
                parts = name_raw.strip('"').split(",")
                name = (parts[1].strip() + " " + parts[0].strip()) if len(parts) >= 2 else name_raw
                
                pitchers[name] = {
                    "xERA": float(row["xera"]) if row.get("xera") else 4.2,
                    "xwOBA": float(row.get("est_woba", 0.320)),
                    "ERA": float(row["era"]) if row.get("era") else 4.2,
                    "pa": pa,
                }
            except: continue
    print(f"  Pitcher xStats: {len(pitchers)} starters")
    return pitchers

def build_js_data(model, t_bat, t_pit, pitchers):
    """Generate JavaScript code block with model + data."""
    
    weights = model["weights"]
    bias = model["bias"]
    features = model["features"]
    
    # Remap team stats to full Odds API names
    t_bat_full = {full_name(k): v for k, v in t_bat.items()}
    t_pit_full = {full_name(k): v for k, v in t_pit.items()}
    park_full = {full_name(k): v for k, v in {
        "COL":1.25,"CIN":1.08,"TEX":1.06,"BOS":1.05,"PHI":1.04,
        "CHC":1.03,"MIL":1.02,"ATL":1.02,"MIN":1.01,"BAL":1.01,
        "TOR":1.01,"NYY":1.00,"DET":1.00,"ARI":1.00,"CLE":0.99,
        "LAA":0.99,"HOU":0.99,"KC":0.98,"CHW":0.98,"WSH":0.98,
        "STL":0.97,"NYM":0.97,"SF":0.96,"PIT":0.96,"SD":0.95,
        "LAD":0.95,"TB":0.94,"SEA":0.93,"MIA":0.92,"OAK":0.93,
    }.items()}
    tz_full = {full_name(k): v for k, v in {
        "NYY":0,"NYM":0,"BOS":0,"PHI":0,"BAL":0,"WSH":0,"PIT":0,"ATL":0,
        "MIA":0,"TB":0,"TOR":0,"DET":0,"CLE":0,"CIN":0,
        "CHC":1,"CHW":1,"MIL":1,"MIN":1,"STL":1,"KC":1,"HOU":1,"TEX":1,
        "COL":2,"ARI":2,
        "LAD":3,"LAA":3,"SD":3,"SF":3,"OAK":3,"SEA":3,
    }.items()}
    
    js = """
// ═══════════════════════════════════════════════════════════
// MLB MODEL v11b — 24 features, trained 2021-2023, tested 2025
// Test: 59% accuracy, +25.8% ROI at 12%+ edge (closing lines)
// ═══════════════════════════════════════════════════════════
var V11B_BIAS = """ + str(round(bias, 6)) + """;
var V11B_WEIGHTS = """ + json.dumps({k: round(v, 6) for k, v in weights.items()}, indent=2) + """;
var V11B_FEATURES = """ + json.dumps(features) + """;

// Team batting stats (2025 FanGraphs) — update periodically during 2026 season
var TEAM_BAT = """ + json.dumps({k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in t_bat_full.items()}, indent=2) + """;

// Team pitching stats (2025 FanGraphs)
var TEAM_PIT = """ + json.dumps({k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in t_pit_full.items()}, indent=2) + """;

// Pitcher Statcast lookup (2025, 100+ PA starters)
var PITCHER_XS = """ + json.dumps({k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in pitchers.items()}, indent=2) + """;

// Park factors (by full team name)
var PARK_FACTORS_V11B = """ + json.dumps({k: round(v, 3) for k, v in park_full.items()}) + """;

// Team timezones (by full team name)  
var TEAM_TZ_V11B = """ + json.dumps(tz_full) + """;

var MLB_BET_THRESHOLD = 0.12; // 12% edge (backtested optimal for v11b)

function v11bPredict(homeTeam, awayTeam, homePitcher, awayPitcher, homeRoll, awayRoll) {
    // Get team stats (fall back to league average)
    var hb = TEAM_BAT[homeTeam] || {wRC:100,OPS:0.720,xwOBA:0.320,Barrel:0.07,EV:88.5};
    var ab = TEAM_BAT[awayTeam] || {wRC:100,OPS:0.720,xwOBA:0.320,Barrel:0.07,EV:88.5};
    var hp = TEAM_PIT[homeTeam] || {ERA:4.0,FIP:4.0,BB9:3.2,xwOBA:0.320};
    var ap = TEAM_PIT[awayTeam] || {ERA:4.0,FIP:4.0,BB9:3.2,xwOBA:0.320};
    
    // Get pitcher Statcast
    var hsp = PITCHER_XS[homePitcher] || {xERA:4.2,xwOBA:0.320,ERA:4.2};
    var asp = PITCHER_XS[awayPitcher] || {xERA:4.2,xwOBA:0.320,ERA:4.2};
    
    // Rolling records (from app's fatigue/schedule data)
    var hr = homeRoll || {l10_wp:0.5,l30_wp:0.5,l10_rd:0,srs:0,sra:0,sg:0,rest:3,g_in_3:2};
    var ar = awayRoll || {l10_wp:0.5,l30_wp:0.5,l10_rd:0,srs:0,sra:0,sg:0,rest:3,g_in_3:2};
    
    // Pythagorean
    function pyth(rs,ra){if(rs+ra===0)return 0.5;var e=1.83;return Math.pow(rs,e)/(Math.pow(rs,e)+Math.pow(ra,e));}
    
    // Park factor
    var park = PARK_FACTORS_V11B[homeTeam] || 1.0;
    
    // Travel
    var travel = Math.abs((TEAM_TZ_V11B[homeTeam]||1) - (TEAM_TZ_V11B[awayTeam]||1)) / 3;
    
    // Bullpen ERA proxy
    var hPen = Math.max(2, Math.min(7, (hp.ERA - 0.55*hsp.ERA) / 0.45));
    var aPen = Math.max(2, Math.min(7, (ap.ERA - 0.55*asp.ERA) / 0.45));
    
    // Build feature vector
    var f = {
        f_home: 1.0,
        f_pyth: pyth(hr.srs,hr.sra) - pyth(ar.srs,ar.sra),
        f_l10: hr.l10_wp - ar.l10_wp,
        f_l30: hr.l30_wp - ar.l30_wp,
        f_l10_rd: (hr.l10_rd - ar.l10_rd) / 5,
        f_wrc: (hb.wRC - ab.wRC) / 100,
        f_ops: hb.OPS - ab.OPS,
        f_xwoba_bat: hb.xwOBA - ab.xwOBA,
        f_barrel: hb.Barrel - ab.Barrel,
        f_ev: (hb.EV - ab.EV) / 10,
        f_era: ap.ERA - hp.ERA,
        f_fip: ap.FIP - hp.FIP,
        f_bb9: (ap.BB9 - hp.BB9) / 3,
        f_sp_xera: (asp.xERA - hsp.xERA) / 2,
        f_sp_xwoba: (asp.xwOBA - hsp.xwOBA) * 5,
        f_matchup: (asp.xwOBA * hb.wRC / 100) - (hsp.xwOBA * ab.wRC / 100),
        f_pen: (aPen - hPen) / 2,
        f_park: park,
        f_rest_diff: Math.min(3, (hr.rest - ar.rest)) / 3,
        f_sched: (ar.g_in_3 - hr.g_in_3) / 3,
        f_travel: travel,
        f_sp_x_bat: ((asp.xERA - hsp.xERA) / 2) * ((hb.wRC - ab.wRC) / 100),
        f_pen_x_sched: ((aPen - hPen) / 3) * ((ar.g_in_3 - hr.g_in_3) / 3),
        f_form_x_rd: (hr.l10_wp - ar.l10_wp) * ((hr.l10_rd - ar.l10_rd) / 5),
    };
    
    // Logistic regression
    var z = V11B_BIAS;
    V11B_FEATURES.forEach(function(feat) {
        z += (V11B_WEIGHTS[feat] || 0) * (f[feat] || 0);
    });
    return 1.0 / (1.0 + Math.exp(-Math.max(-500, Math.min(500, z))));
}
"""
    return js


def patch_app(js_data):
    """Read current index.html, inject model, remove props, set threshold."""
    app_path = APP_DIR / "index.html"
    html = app_path.read_text()
    
    # 1. Inject model code after the NHL_TZ block
    # Find a reliable anchor point
    anchor = "// ── STATE ──"
    idx = html.find(anchor)
    if idx < 0:
        # Try alternate anchor
        anchor = "var S={"
        idx = html.find(anchor)
    if idx < 0:
        print("ERROR: Could not find injection point")
        return None
    html = html[:idx] + js_data + "\n\n" + html[idx:]
    print("  ✓ Injected v11b model code")
    
    # 2. Remove props from tab list
    old_tabs = '{k:"props",l:"Player Props",i:"🎯"},'
    if old_tabs in html:
        html = html.replace(old_tabs, '')
        print("  ✓ Removed Props tab")
    
    # 3. Remove props from refreshAll
    old_refresh = 'await Promise.allSettled([loadMLBProps(),loadNHLProps()]);'
    if old_refresh in html:
        html = html.replace(old_refresh, '// Props removed in v11b')
        print("  ✓ Removed props from refreshAll")
    
    # Remove propsLoaded reset
    html = html.replace('S.mlb.propsLoaded=false;S.nhl.propsLoaded=false;', '')
    
    # 4. Disable prop pills row 
    html = html.replace(
        'if(S.tab==="props"){\n    h+=\'<div class="prow">\';',
        'if(false){\n    h+=\'<div class="prow">\';'
    )
    
    # 5. Disable prop bets from Bets tab
    html = html.replace(
        '      // Prop bets from ALL markets (if loaded)',
        '      // Prop bets DISABLED in v11b\n      if(false) // was: prop bets'
    )
    
    # 6. Remove props badge from bets tab
    html = html.replace(
        """if(!nhlProps||!mlbProps)h+='<div style="padding:3px 10px;border-radius:5px;background:var(--alt);font-size:10px;color:var(--td)">""" + """💡 Load props in each league\\'s Props tab to include prop bets</div>';""",
        ''
    )
    
    # 7. Update MLB bet threshold: 10% → 12%
    html = html.replace('var betThresh=10; // MLB default', 'var betThresh=12; // MLB v11b optimal')
    html = html.replace(
        'var thresh3=sNHL?(side3==="HOME"?5:7):10;',
        'var thresh3=sNHL?(side3==="HOME"?5:7):12;'
    )
    print("  ✓ MLB threshold → 12%")
    
    # 8. Inject v11b model integration into render
    # This block runs AFTER games are loaded but BEFORE ML tab renders
    # It recalculates fair probabilities for MLB using the model
    model_integration = """
    // ── v11b MODEL INTEGRATION (MLB only) ──
    if(!isNHL && typeof v11bPredict === 'function' && S.mlb.lineups){
      games.forEach(function(g){
        var info=S.mlb.lineups[g.home]||{};
        var hRoll={l10_wp:0.5,l30_wp:0.5,l10_rd:0,srs:0,sra:0,sg:0,rest:3,g_in_3:2};
        var aRoll={l10_wp:0.5,l30_wp:0.5,l10_rd:0,srs:0,sra:0,sg:0,rest:3,g_in_3:2};
        var hFat=S.mlb.fatigue[g.home]||{};
        var aFat=S.mlb.fatigue[g.away]||{};
        if(hFat.minRest)hRoll.rest=hFat.minRest;
        if(aFat.minRest)aRoll.rest=aFat.minRest;
        if(hFat.games)hRoll.g_in_3=hFat.games;
        if(aFat.games)aRoll.g_in_3=aFat.games;
        var hP=info.homePitcher||'TBD';
        var aP=info.awayPitcher||'TBD';
        var mp=v11bPredict(g.home,g.away,hP,aP,hRoll,aRoll);
        g.modelHome=+(mp*100).toFixed(1);
        g.modelAway=+((1-mp)*100).toFixed(1);
        // Blend: 60% model + 40% consensus
        if(g.fairH>0){
          g.fairH=+(0.6*g.modelHome+0.4*g.fairH).toFixed(1);
          g.fairA=+(0.6*g.modelAway+0.4*g.fairA).toFixed(1);
        }
        // Recalculate edges
        var bHI=ml2p(g.bestHML),bAI=ml2p(g.bestAML);
        if(bHI&&bAI){
          g.hEdge=+((1/bHI)*(g.fairH/100)*100-100).toFixed(1);
          g.aEdge=+((1/bAI)*(g.fairA/100)*100-100).toFixed(1);
          g.topEdge=Math.max(g.hEdge,g.aEdge);
          g.betSide=g.topEdge>3?(g.hEdge>=g.aEdge?"HOME":"AWAY"):null;
        }
      });
    }

"""
    
    # Find the right injection point — after games are sorted but before ML tab renders
    inject_before = "// Recount bets/watches"
    idx2 = html.find(inject_before)
    if idx2 > 0:
        html = html[:idx2] + model_integration + html[idx2:]
        print("  ✓ Injected model integration into render loop")
    else:
        print("  ⚠ Could not find render injection point")
    
    # 9. Update version strings
    html = html.replace('v10</span>', 'v11b</span>')
    html = html.replace('DIAMOND EDGE v10', 'DIAMOND EDGE v11b')
    
    # 10. Update status bar
    html = html.replace(
        '(isNHL?"ROI +14.8%":"CLV +0.46%")',
        '(isNHL?"ROI +14.8%":"v11b +26% ROI")'
    )
    html = html.replace(
        '(isNHL?"at 5%+ edge":"backtested")',
        '(isNHL?"at 5%+ edge":"12%+ edge")'
    )
    
    # 11. Update footer
    html = html.replace(
        'MLB: 40,996 games backtested',
        'MLB: v11b model · 24 features'
    )
    html = html.replace(
        'CLV +0.46% · 10%+ edge threshold',
        '59% accuracy · +26% ROI at 12%+'
    )
    
    print("  ✓ Updated version + labels")
    return html


def main():
    print("Diamond Edge — App Builder (v11b)")
    print("=" * 50)
    
    print("\nLoading model...")
    model = load_model()
    print(f"  Features: {len(model['features'])}")
    print(f"  Bias: {model['bias']:.6f}")
    print(f"  Test accuracy: {model.get('test_accuracy', 'N/A')}")
    
    print("\nLoading team stats...")
    t_bat = load_team_batting_2025()
    t_pit = load_team_pitching_2025()
    pitchers = load_pitcher_xstats_2025()
    
    print("\nGenerating JavaScript data block...")
    js_data = build_js_data(model, t_bat, t_pit, pitchers)
    print(f"  JS block: {len(js_data)} chars")
    
    print("\nPatching app...")
    html = patch_app(js_data)
    if html is None:
        print("FAILED — could not patch app")
        return
    
    # Write output
    out_path = APP_DIR / "index.html"
    out_path.write_text(html)
    print(f"\n  Written → {out_path}")
    print(f"  Size: {len(html):,} chars")
    
    print(f"\nDone! Deploy with:")
    print(f"  cd ~/Desktop/diamond-edge && git add -A && git commit -m 'v11b model' && git push")


if __name__ == "__main__":
    main()
