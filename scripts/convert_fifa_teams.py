#!/usr/bin/env python3
"""Convert AgentPitch FIFA2026 YAML teams → frontend JSON format.

Usage:
    python scripts/convert_fifa_teams.py

Reads AgentPitch/fifa2026/teams/*.yaml, converts to
frontend/public/data/teams/nation/*.json with mapped attributes and positions.
"""

import json
import math
import os
import re
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "AgentPitch" / "fifa2026" / "teams"
DST_DIR = ROOT / "frontend" / "public" / "data" / "teams" / "nation"
NATIONS_INDEX = ROOT / "frontend" / "public" / "data" / "teams" / "nations.json"

# ─── Attribute mapping: AgentPitch (1-20) → frontend (0-100) ───

def map_attrs(p: dict, role: str) -> dict:
    """Convert AgentPitch player attributes to frontend format."""
    attrs = {
        "pace": min(100, max(1, int(p.get("speed", 10) * 5))),
        "shooting": min(100, max(1, int(p.get("shoot", 10) * 5))),
        "passing": min(100, max(1, int(p.get("pass", 10) * 5))),
        "dribbling": min(100, max(1, int(p.get("dribbling", 10) * 5))),
        "defending": min(100, max(1, int(
            p.get("save", 10) * 5 if role == "GK" else (p.get("strength", 10) * 3 + p.get("discipline", 10) * 2)
        ))),
        "physicality": min(100, max(1, int(p.get("strength", 10) * 5))),
        "stamina": min(100, max(1, int(p.get("stamina", 10) * 5))),
        "awareness": min(100, max(1, int(
            (p.get("skill", 10) * 3 + p.get("discipline", 10) * 2)
        ))),
        "composure": min(100, max(1, int(p.get("skill", 10) * 5))),
    }
    overall = round(sum(attrs.values()) / 9)
    return attrs, overall


# ─── Role → Position mapping ───

# Assign specific positions based on order within role group and formation
def assign_positions(players: list[dict]) -> list[str]:
    """Assign frontend position strings based on AgentPitch roles and formation."""
    role_count = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
    for p in players:
        role_count[p["role"]] += 1

    positions = []
    def_i = {"CB": 0, "LB": 0, "RB": 0}
    mid_i = {"CM": 0, "LM": 0, "RM": 0, "CDM": 0, "CAM": 0}
    att_i = {"ST": 0, "LW": 0, "RW": 0, "CF": 0}

    for p in players:
        role = p["role"]
        if role == "GK":
            positions.append("GK")

        elif role == "DEF":
            # Distribute: first 2 → CB, then LB, then RB
            nd = role_count["DEF"]
            d = def_i["CB"] + def_i["LB"] + def_i["RB"]
            if nd <= 3:
                opts = ["CB", "CB", "CB"][d:d+1] if nd == 3 else (["CB", "LB"] if nd == 2 else ["CB"])
                pos = opts[0]
            elif nd == 4:
                pos = ["CB", "CB", "LB", "RB"][d]
            else:
                pos = ["CB", "CB", "LB", "RB", "CB"][min(d, 4)]
            def_i[pos] += 1
            positions.append(pos)

        elif role == "MID":
            nd = role_count["MID"]
            m = mid_i["CM"] + mid_i["LM"] + mid_i["RM"] + mid_i["CDM"] + mid_i["CAM"]
            if nd == 2:
                pos = ["CM", "CM"][m]
            elif nd == 3:
                pos = ["CM", "CM", "LM"][m]
            elif nd == 4:
                pos = ["CM", "CM", "LM", "RM"][m]
            elif nd == 5:
                pos = ["CDM", "CM", "CM", "LM", "RM"][m]
            else:
                pos = "CM"
            mid_i[pos] += 1
            positions.append(pos)

        elif role == "FWD":
            na = role_count["FWD"]
            a = att_i["ST"] + att_i["LW"] + att_i["RW"] + att_i["CF"]
            if na == 1:
                pos = "ST"
            elif na == 2:
                pos = ["ST", "CF"][a]
            elif na == 3:
                pos = ["ST", "LW", "RW"][a]
            else:
                pos = ["ST", "LW", "RW", "CF"][min(a, 3)]
            att_i[pos] += 1
            positions.append(pos)

    return positions


# ─── Load existing frontend data for image preservation ───

def load_existing() -> dict[str, dict]:
    """Load existing frontend JSON files to preserve images and logos."""
    existing = {}
    if not DST_DIR.exists():
        return existing
    for f in DST_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            existing[data.get("name", "").lower()] = data
        except Exception:
            pass
    return existing


def find_image(name: str, existing_players: list[dict]) -> str:
    """Fuzzy match a player name to an existing player to preserve their image."""
    def word_set(s: str) -> set[str]:
        return set(re.sub(r"[^a-z\s]", "", s.lower()).split())
    name_words = word_set(name)
    best, best_score = "", 0
    for ep in existing_players:
        ep_words = word_set(ep.get("name", ""))
        # Score by common words, require at least 2 matching words
        common = name_words & ep_words
        score = len(common)
        # Boost for prefix match on first word
        nw = sorted(name_words)
        ew = sorted(ep_words)
        if nw and ew and ew[0].startswith(nw[0][:4]):
            score += 3
        if score > best_score:
            best_score = score
            best = ep.get("image", "")
    return best if best_score >= 2 else ""


# ─── Convert one team ───

def convert_team(yaml_path: Path, existing: dict) -> dict | None:
    """Convert a single YAML file to frontend JSON format."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    name = data.get("name", "")
    logo = ""
    existing_players = []
    tactical_document = ""

    # Load tactical document from tactices/ directory
    tactic_path = ROOT / "AgentPitch" / "fifa2026" / "tactices" / f"{yaml_path.stem}.md"
    if tactic_path.exists():
        tactical_document = tactic_path.read_text(encoding="utf-8").strip()

    if name.lower() in existing:
        logo = existing[name.lower()].get("logo", "")
        existing_players = existing[name.lower()].get("players", [])

    players = []
    raw_players = data.get("players", [])
    positions = assign_positions(raw_players)

    for i, p in enumerate(raw_players):
        attrs, overall = map_attrs(p, p["role"])
        pos = positions[i] if i < len(positions) else p["role"]
        image = find_image(p["name"], existing_players)
        players.append({
            "name": p["name"],
            "number": p.get("number", i + 1),
            "position": pos,
            "overall": overall,
            "attributes": attrs,
            "image": image,
        })

    return {
        "name": name,
        "type": "nation",
        "logo": logo,
        "players": players,
        "tactical_document": tactical_document,
    }


# ─── Main ───

def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_existing()

    nations_index = []
    converted = 0
    skipped = 0

    for yf in sorted(SRC_DIR.glob("*.yaml")):
        team = convert_team(yf, existing)
        if team is None:
            skipped += 1
            continue

        out_name = re.sub(r"[^a-zA-Z0-9_]", "_", yf.stem)
        # Capitalize first letter: 'argentina' → 'Argentina'
        out_name = out_name[0].upper() + out_name[1:] if out_name else out_name
        # Match existing file if one already exists (preserve exact casing)
        out_path = DST_DIR / f"{out_name}.json"
        for ex in DST_DIR.iterdir():
            if ex.name.lower() == f"{out_name.lower()}.json":
                out_path = ex
                break
        json.dump(team, open(out_path, "w"), indent=2, ensure_ascii=False)
        nations_index.append({
            "name": team["name"],
            "type": "nation",
            "file": f"nation/{out_path.name}",
            "players": len(team["players"]),
            "logo": team["logo"],
        })
        converted += 1
        print(f"  {team['name']}: {len(team['players'])} players → {out_name}.json")

    # Update nations.json index
    existing_index = []
    if NATIONS_INDEX.exists():
        existing_index = json.load(open(NATIONS_INDEX)).get("teams", [])

    # Merge: replace teams that were converted, keep others
    converted_names = {t["name"] for t in nations_index}
    merged = [t for t in existing_index if t["name"] not in converted_names] + nations_index
    merged.sort(key=lambda t: t["name"])

    json.dump({"teams": merged}, open(NATIONS_INDEX, "w"), indent=2, ensure_ascii=False)

    print(f"\nConverted {converted} teams, {skipped} skipped")
    print(f"Nations index: {len(merged)} total entries")
    print(f"Output: {DST_DIR}")


if __name__ == "__main__":
    main()
