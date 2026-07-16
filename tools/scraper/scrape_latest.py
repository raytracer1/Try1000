#!/usr/bin/env python3
"""Scrape SoFIFA with manual Cloudflare bypass. Uses API interception."""

import json, os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).parent.parent.parent / "frontend" / "public" / "data" / "teams"

POS_MAP = {
    "GK": "GK", "CB": "CB", "LB": "LB", "LWB": "LB", "RB": "RB", "RWB": "RB",
    "CDM": "CDM", "CM": "CM", "CAM": "CAM",
    "LM": "LW", "LW": "LW", "LF": "LW", "RM": "RW", "RW": "RW", "RF": "RW",
    "CF": "ST", "ST": "ST",
}

ATTR_MAP = {
    "sprint_speed": "pace", "acceleration": "pace",
    "finishing": "shooting", "short_passing": "passing",
    "dribbling": "dribbling", "standing_tackle": "defending",
    "strength": "physicality", "stamina": "stamina",
    "reactions": "awareness", "composure": "composure",
}

GK_ATTR = {
    "gk_diving": "pace", "gk_reflexes": "shooting", "gk_handling": "passing",
    "gk_positioning": "dribbling", "gk_reflexes": "defending",
    "strength": "physicality", "stamina": "stamina",
    "reactions": "awareness", "composure": "composure",
}


def parse_pos(s):
    if not s: return "CM"
    for p in str(s).replace(" ", "").split(","):
        p = p.strip().upper()
        if p in POS_MAP: return POS_MAP[p]
    return "CM"


def parse_player(p: dict) -> dict | None:
    try:
        name = str(p.get("name") or p.get("player_name") or p.get("full_name", "")).strip()
        if not name: return None

        pos_str = str(p.get("position") or p.get("positions") or "CM")
        pos = parse_pos(pos_str)
        is_gk = (pos == "GK")

        ovr = 70
        v = p.get("overall_rating") or p.get("overall") or p.get("ovr", 70)
        try: ovr = int(float(str(v)))
        except: pass

        attrs = {}
        m = GK_ATTR if is_gk else ATTR_MAP
        for k, v2 in m.items():
            val = p.get(k, 0)
            try: attrs[v2] = min(99, max(1, int(float(str(val)))))
            except: attrs[v2] = 70

        img = str(p.get("image") or p.get("player_face_url") or "")
        return {"name": name, "number": 0, "position": pos, "overall": ovr, "attributes": attrs, "image": img}
    except:
        return None


def find_players(obj, depth=0) -> list | None:
    """Recursively search for player list in JSON."""
    if depth > 10: return None
    if isinstance(obj, list) and len(obj) >= 11:
        if all(isinstance(x, dict) and ("name" in x or "player_name" in x or "overall" in str(x)) for x in obj[:5]):
            return obj
    if isinstance(obj, dict):
        for k in obj:
            r = find_players(obj[k], depth + 1)
            if r: return r
    return None


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "club").mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        collected = []

        # Intercept ALL JSON API responses
        page.on("response", lambda r: (
            collected.append({"u": r.url, "b": r.json()})
            if r.ok and "json" in (r.headers.get("content-type") or "") else None
        ))

        # Navigate to teams page — user solves CF
        print("Opening SoFIFA. Solve CAPTCHA in the browser, then press Enter...")
        page.goto("https://sofifa.com/teams?type=club", timeout=120000, wait_until="load")
        input("Press Enter when page has loaded...")
        page.wait_for_timeout(2000)

        # Extract team list from collected API data
        all_team_ids = set()
        for c in collected:
            ids = re_find_all(r'"team_id"\s*:\s*(\d+)', json.dumps(c.get("b", {})))
            all_team_ids.update(ids)
            # Also try finding team objects
            if isinstance(c.get("b"), list):
                for item in c["b"]:
                    if isinstance(item, dict) and item.get("team_id"):
                        all_team_ids.add(int(item["team_id"]))

        # Fallback: scrape links
        if not all_team_ids:
            print("No API data found — scraping links...")
            links = page.query_selector_all("a[href*='/team/']")
            for l in links:
                h = l.get_attribute("href") or ""
                try:
                    tid = int(h.split("/team/")[1].split("/")[0])
                    if tid > 0: all_team_ids.add(tid)
                except: pass

        team_ids = sorted(all_team_ids)
        print(f"Found {len(team_ids)} team IDs")

        club_teams = []
        for i, tid in enumerate(team_ids[:200]):  # limit to 200
            url = f"https://sofifa.com/team/{tid}"
            print(f"\n[{i+1}/{min(len(team_ids), 200)}] ID={tid} — {url}")
            collected.clear()

            page.goto(url, timeout=120000, wait_until="load")
            print("    (if Cloudflare blocks, solve the CAPTCHA in the browser)")
            input("    Press Enter when the player data has loaded...")

            # Search collected API data for players
            players = None
            for c in collected:
                players = find_players(c.get("b", {}))
                if players: break

            # Fallback: page content
            if not players:
                content = page.content()
                import re as _re
                # Try embedded JSON
                matches = _re.findall(r'__NEXT_DATA__["\']?\s*:\s*({.+?})\s*</script>', content, _re.DOTALL)
                for m in matches:
                    try:
                        data = json.loads(m)
                        players = find_players(data)
                        if players: break
                    except: pass

            if not players:
                print("    ❌ No player data found")
                continue

            parsed = [x for x in [parse_player(p) for p in players] if x]
            if len(parsed) < 11:
                print(f"    ❌ Only {len(parsed)} players parsed")
                continue

            parsed.sort(key=lambda x: -x["overall"])
            squad = parsed[:23]
            for j, p in enumerate(squad): p["number"] = j + 1

            # Get team name
            tname = f"Team_{tid}"
            for c in collected:
                b = c.get("b", {})
                if isinstance(b, dict) and b.get("name"):
                    tname = str(b["name"]).strip()
                    break

            safe = tname.replace("/", "-").replace(" ", "_")
            fp = OUTPUT / "club" / f"{safe}.json"
            json.dump({"name": tname, "type": "club", "players": squad}, open(fp, "w"), ensure_ascii=False, indent=2)
            club_teams.append({"name": tname, "type": "club", "file": f"club/{safe}.json", "players": len(squad)})
            print(f"    ✅ {tname}: {len(squad)} players")

        # Save index
        json.dump({"teams": sorted(club_teams, key=lambda t: t["name"])},
                  open(OUTPUT / "clubs.json", "w"), ensure_ascii=False, indent=2)
        browser.close()

    print(f"\nDone! {len(club_teams)} teams → {OUTPUT}/")


import re as _re2
def re_find_all(pattern, text):
    return [int(x) for x in _re2.findall(pattern, str(text)) if x.isdigit()]

if __name__ == "__main__":
    main()
