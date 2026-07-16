#!/usr/bin/env python3
"""Scrape SoFIFA for player data.

SoFIFA is a Next.js SSR site — player data is embedded in the HTML
as JSON in <script id="__NEXT_DATA__">. No JavaScript rendering needed.

Usage:
    pip install requests beautifulsoup4
    python scrape_sofifa.py --leagues "Premier League,La Liga" --max-teams 5
"""

import json
import os
import re
import sys
import time
import requests
from pathlib import Path
from collections import defaultdict
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

POS_MAP = {
    "GK": "GK", "CB": "CB",
    "LB": "LB", "LWB": "LB", "RB": "RB", "RWB": "RB",
    "CDM": "CDM", "CM": "CM", "CAM": "CAM",
    "LM": "LW", "LW": "LW", "RM": "RW", "RW": "RW",
    "CF": "ST", "ST": "ST",
}

ATTR_MAP = {
    "pac": "pace", "sho": "shooting", "pas": "passing",
    "dri": "dribbling", "def": "defending", "phy": "physicality",
    "sta": "stamina",
}

session = requests.Session()
session.headers.update(HEADERS)


def get_team_list(league_name: str) -> list[dict]:
    """Search SoFIFA for teams in a league and return list of {id, name}."""
    url = f"https://sofifa.com/teams?type=club"
    resp = session.get(url, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        print(f"  Could not find __NEXT_DATA__ (got {len(resp.text)} bytes)")
        return []

    data = json.loads(script.string)
    teams = []
    try:
        # Next.js data structure varies — look for team list
        props = data.get("props", {}).get("pageProps", {})
        team_list = props.get("teams", props.get("initialData", props.get("data", [])))
        if isinstance(team_list, list):
            for t in team_list:
                if league_name.lower() in str(t.get("league", "")).lower():
                    teams.append({"id": t.get("id"), "name": t.get("name", t.get("title", ""))})
        if not teams:
            # Try deeper search
            for key, val in data.items():
                if isinstance(val, dict):
                    for k2, v2 in val.items():
                        if isinstance(v2, list) and len(v2) > 10:
                            for item in v2:
                                if isinstance(item, dict) and "league" in str(item).lower():
                                    if league_name.lower() in str(item.get("league", "")).lower():
                                        teams.append({"id": item.get("id"), "name": item.get("name", "")})
    except Exception as e:
        print(f"  Error parsing team list: {e}")
    return teams[:50]


def get_players(team_id: int, team_name: str) -> list[dict]:
    """Scrape players from a team page."""
    url = f"https://sofifa.com/team/{team_id}/{team_name.lower().replace(' ', '-')}"
    print(f"  Fetching {url}...")
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"    HTTP {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        print(f"    No __NEXT_DATA__ found")
        return []

    data = json.loads(script.string)
    players = []
    try:
        # Navigate the Next.js data structure
        props = data.get("props", {}).get("pageProps", {})
        team_data = props.get("team", props.get("data", {}))
        player_list = team_data.get("players", props.get("players", []))

        if not player_list:
            # Try alternate paths
            for key in data:
                val = data[key]
                if isinstance(val, dict):
                    for sub in val.values():
                        if isinstance(sub, list) and len(sub) >= 11:
                            first = sub[0]
                            if isinstance(first, dict) and "overall" in str(first).lower():
                                player_list = sub
                                break
    except Exception as e:
        print(f"    Parse error: {e}")

    for p in player_list:
        try:
            attrs = {}
            raw = p.get("stats", p.get("attributes", p))
            # Try shortcut attribute names first (pac, sho, etc.)
            for short, long in ATTR_MAP.items():
                val = raw.get(short, raw.get(long, 0))
                try:
                    attrs[long] = min(99, max(1, int(float(val))))
                except (ValueError, TypeError):
                    attrs[long] = 70
            attrs.setdefault("awareness", raw.get("awr", raw.get("reactions", 70)))
            attrs.setdefault("composure", raw.get("com", raw.get("composure", 70)))
            for k in list(attrs.keys()):
                try:
                    attrs[k] = int(float(attrs[k]))
                except (ValueError, TypeError):
                    attrs[k] = 70

            pos = str(p.get("position", p.get("pos", "CM"))).upper()
            players.append({
                "name": str(p.get("name", p.get("player_name", ""))),
                "number": int(p.get("number", p.get("kit", 0)) or 0),
                "position": POS_MAP.get(pos, "CM"),
                "overall": int(float(p.get("overall", p.get("ovr", 70)))),
                "attributes": {k: max(1, min(99, attrs[k])) for k in attrs},
            })
        except Exception:
            continue

    return players


def scrape_leagues(leagues: list[str], max_teams_per_league: int, output_dir: str):
    """Main scraper — iterate over leagues, get teams, scrape players."""
    os.makedirs(output_dir, exist_ok=True)
    all_teams = []

    for league in leagues:
        print(f"\n{'='*50}\nLeague: {league}\n{'='*50}")
        teams = get_team_list(league)
        print(f"  Found {len(teams)} teams")

        for i, team in enumerate(teams[:max_teams_per_league]):
            print(f"\n[{i+1}/{min(len(teams), max_teams_per_league)}] {team['name']}")
            time.sleep(1)  # be polite

            players = get_players(team["id"], team["name"])
            if not players:
                print("    (no players)")
                continue

            safe = team["name"].replace("/", "-").replace(" ", "_")
            file_path = Path(output_dir) / "club" / f"{safe}.json"
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"name": team["name"], "type": "club", "players": players[:23]},
                          f, ensure_ascii=False, indent=2)

            all_teams.append({"name": team["name"], "type": "club",
                              "file": f"club/{safe}.json", "players": len(players[:23])})
            print(f"    Saved {len(players[:23])} players")

    # Write index
    with open(Path(output_dir) / "index.json", "w", encoding="utf-8") as f:
        json.dump({"teams": sorted(all_teams, key=lambda t: t["name"])}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done: {len(all_teams)} teams scraped")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--leagues", default="Premier League,La Liga,Serie A,Bundesliga,Ligue 1",
                        help="Comma-separated league names")
    parser.add_argument("--max-teams", type=int, default=5, help="Max teams per league")
    parser.add_argument("--out", default="../../frontend/public/data/teams")
    args = parser.parse_args()

    scrape_leagues([l.strip() for l in args.leagues.split(",")], args.max_teams, args.out)
