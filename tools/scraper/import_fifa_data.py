#!/usr/bin/env python3
"""Import EA FC player data from CSV → team JSON files.

Supports both formats:
1. SoFIFA scraper CSV (prashantghimire/sofifa-web-scraper)
2. Kaggle FIFA22+ dataset

Output: frontend/public/data/teams/{club, nation}/{TeamName}.json
"""

import csv, json, os, sys
from collections import defaultdict
from pathlib import Path

# ─── Column detection ───

SOFIFA_ATTR_MAP = {
    "movement_sprint_speed": "pace", "attacking_finishing": "shooting",
    "attacking_short_passing": "passing", "skill_dribbling": "dribbling",
    "defending_standing_tackle": "defending", "power_strength": "physicality",
    "power_stamina": "stamina", "movement_reactions": "awareness",
    "mentality_composure": "composure",
}

KAGGLE_ATTR_MAP = {
    "SprintSpeed": "pace", "Finishing": "shooting", "ShortPassing": "passing",
    "Dribbling": "dribbling", "StandingTackle": "defending", "Strength": "physicality",
    "Stamina": "stamina", "Reactions": "awareness", "Composure": "composure",
}

# For GKs, use GK-specific stats mapped to our system
GK_ATTR_MAP = {
    "GKDiving": "pace", "GKReflexes": "shooting", "GKHandling": "passing",
    "GKPositioning": "dribbling", "GKReflexes": "defending", "Strength": "physicality",
    "Stamina": "stamina", "Reactions": "awareness", "Composure": "composure",
}

POS_MAP = {
    "GK": "GK", "CB": "CB", "LCB": "CB", "RCB": "CB",
    "LB": "LB", "LWB": "LB", "RB": "RB", "RWB": "RB",
    "CDM": "CDM", "CM": "CM", "LCM": "CM", "RCM": "CM",
    "CAM": "CAM", "LM": "LW", "LW": "LW", "LF": "LW",
    "RM": "RW", "RW": "RW", "RF": "RW", "CF": "ST", "ST": "ST",
}


def detect_format(headers):
    """Detect whether this is a SoFIFA scraper or Kaggle FIFA dataset."""
    if "club_name" in headers or "player_id" in headers:
        return "sofifa", SOFIFA_ATTR_MAP, "club_name", "country_name", "name", "positions", "overall_rating"
    if "Club" in headers and "SprintSpeed" in headers:
        return "kaggle", KAGGLE_ATTR_MAP, "Club", "Nationality", "Name", "Position", "Overall"
    return "unknown", {}, "", "", "", "", ""


def parse_position(pos_str):
    if not pos_str: return "CM"
    # Strip HTML tags (Kaggle format sometimes has <span> tags)
    import re
    pos_str = re.sub(r"<[^>]+>", "", pos_str)
    for p in pos_str.replace(" ", "").split(","):
        p = p.strip().upper()
        if p in POS_MAP:
            return POS_MAP[p]
    # Also check Best Position if available
    return "CM"


def import_csv(csv_path: str, output_dir: str):
    players_by_team = defaultdict(list)
    players_by_nation = defaultdict(list)
    seen_club = set()
    seen_nation = set()
    total, skipped = 0, 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        fmt, attr_map, col_club, col_nation, col_name, col_pos, col_ovr = detect_format(headers)

        if fmt == "unknown":
            print("Unknown CSV format. Expected SoFIFA or Kaggle FIFA columns.", file=sys.stderr)
            print(f"Got headers: {headers[:20]}", file=sys.stderr)
            return

        print(f"Detected {fmt} format, {len(headers)} columns")

        for row in reader:
            try:
                name = row.get(col_name, "").strip()
                club = row.get(col_club, "").strip()
                nation = row.get(col_nation, "").strip()
                if not name: continue

                overall = int(float(row.get(col_ovr, "70").strip())) if row.get(col_ovr, "").strip() else 70
                if overall < 60: skipped += 1; continue

                position = parse_position(row.get(col_pos, ""))

                attrs = {}
                is_gk = position == "GK"
                map_to_use = GK_ATTR_MAP if is_gk else attr_map
                for csv_k, our_k in map_to_use.items():
                    val = row.get(csv_k, "").strip()
                    attrs[our_k] = min(99, max(1, int(float(val)))) if val else 70

                player = {"name": name, "number": 0, "position": position, "overall": overall, "attributes": attrs}

                if club and (club, name) not in seen_club:
                    seen_club.add((club, name))
                    players_by_team[club].append(player)
                if nation and (nation, name) not in seen_nation:
                    seen_nation.add((nation, name))
                    players_by_nation[nation].append(player)
                total += 1
            except Exception:
                skipped += 1

    os.makedirs(output_dir, exist_ok=True)
    all_teams = []

    for label, data, prefix in [("club", players_by_team, "club"), ("nation", players_by_nation, "nation")]:
        subdir = Path(output_dir) / prefix
        subdir.mkdir(exist_ok=True)
        for team_name, players in sorted(data.items()):
            if len(players) < 11: continue
            players.sort(key=lambda p: -p["overall"])
            squad = players[:23]
            for i, p in enumerate(squad): p["number"] = i + 1
            safe = team_name.replace("/", "-").replace(" ", "_")
            with open(subdir / f"{safe}.json", "w", encoding="utf-8") as f:
                json.dump({"name": team_name, "type": prefix, "players": squad}, f, ensure_ascii=False, indent=2)
            all_teams.append({"name": team_name, "type": prefix, "file": f"{prefix}/{safe}.json", "players": len(squad)})

    with open(Path(output_dir) / "index.json", "w", encoding="utf-8") as f:
        json.dump({"teams": sorted(all_teams, key=lambda t: t["name"])}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done: {total} players from {len(players_by_team)} clubs + {len(players_by_nation)} nations")
    print(f"   Output: {os.path.abspath(output_dir)}/")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--out", default="../../frontend/public/data/teams")
    import_csv(p.parse_args().csv, p.parse_args().out)
