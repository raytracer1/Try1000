"""Seed demo data. Called by FC on first deploy via init_db(), or manually.

Usage: python seed.py [--reset]
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, init_db
from app.models.user import User
from app.models.team import Team, Player
from app.models.tactic import Tactic
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PLAYER_TEMPLATES = {
    "GK":  {"pace": 50, "shooting": 20, "passing": 60, "dribbling": 30, "defending": 80, "physicality": 70, "stamina": 95, "awareness": 80, "composure": 75},
    "CB":  {"pace": 70, "shooting": 30, "passing": 65, "dribbling": 40, "defending": 82, "physicality": 78, "stamina": 85, "awareness": 75, "composure": 70},
    "LB":  {"pace": 80, "shooting": 40, "passing": 70, "dribbling": 55, "defending": 75, "physicality": 65, "stamina": 85, "awareness": 70, "composure": 70},
    "RB":  {"pace": 80, "shooting": 40, "passing": 70, "dribbling": 55, "defending": 75, "physicality": 65, "stamina": 85, "awareness": 70, "composure": 70},
    "CDM": {"pace": 65, "shooting": 55, "passing": 78, "dribbling": 60, "defending": 78, "physicality": 75, "stamina": 85, "awareness": 78, "composure": 75},
    "CM":  {"pace": 70, "shooting": 65, "passing": 82, "dribbling": 70, "defending": 60, "physicality": 65, "stamina": 82, "awareness": 78, "composure": 78},
    "CAM": {"pace": 75, "shooting": 75, "passing": 85, "dribbling": 82, "defending": 35, "physicality": 55, "stamina": 78, "awareness": 82, "composure": 82},
    "LW":  {"pace": 90, "shooting": 72, "passing": 72, "dribbling": 88, "defending": 30, "physicality": 52, "stamina": 78, "awareness": 72, "composure": 70},
    "RW":  {"pace": 90, "shooting": 72, "passing": 72, "dribbling": 88, "defending": 30, "physicality": 52, "stamina": 78, "awareness": 72, "composure": 70},
    "ST":  {"pace": 82, "shooting": 85, "passing": 65, "dribbling": 78, "defending": 25, "physicality": 68, "stamina": 80, "awareness": 75, "composure": 82},
}

FORMATION = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"]
NAMES = {"GK": "Keeper", "CB": "Defender", "LB": "Fullback", "RB": "Fullback",
         "CDM": "Midfielder", "CM": "Midfielder", "CAM": "Playmaker",
         "LW": "Winger", "RW": "Winger", "ST": "Striker"}


def seed(reset: bool = False):
    db = SessionLocal()

    if db.query(User).filter(User.email == "demo@try1000.io").first():
        if not reset:
            db.close()
            return  # already seeded
        for m in [Tactic, Player, Team, User]:
            db.query(m).delete()
        db.commit()

    user = User(email="demo@try1000.io", username="demo",
                hashed_password=pwd_context.hash("demo123"))
    db.add(user); db.flush()

    teams = []
    for name in ["FC Barcelona", "Manchester City"]:
        t = Team(user_id=user.id, name=name)
        db.add(t); db.flush()
        teams.append(t)

    for team in teams:
        for i, role in enumerate(FORMATION):
            attrs = PLAYER_TEMPLATES[role].copy()
            if team.name == "FC Barcelona":
                attrs["passing"] = min(99, attrs.get("passing", 70) + 5)
                attrs["dribbling"] = min(99, attrs.get("dribbling", 70) + 3)
            else:
                attrs["defending"] = min(99, attrs.get("defending", 70) + 5)
                attrs["physicality"] = min(99, attrs.get("physicality", 70) + 3)
            db.add(Player(team_id=team.id, name=f"{NAMES[role]} {i+1}",
                          number=i+1, position=role, attributes=attrs))
        db.flush()

    for team, tname, style in [
        (teams[0], "Barça 4-3-3", {"pressing_level": 7, "defensive_line": 7, "attacking_width": 8, "tempo": 6, "passing_style": "short", "build_up_style": "slow"}),
        (teams[1], "City 4-3-3",  {"pressing_level": 8, "defensive_line": 8, "attacking_width": 7, "tempo": 8, "passing_style": "mixed", "build_up_style": "balanced"}),
    ]:
        db.add(Tactic(user_id=user.id, team_id=team.id, name=tname, formation="4-3-3", **style))

    db.commit(); db.close()


if __name__ == "__main__":
    init_db()
    seed(reset="--reset" in sys.argv)
    print("✅ Database seeded!\n   User: demo@try1000.io / demo123\n   Teams: FC Barcelona, Manchester City")
