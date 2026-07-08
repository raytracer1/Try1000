"""Team and Player endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.team import Team, Player
from app.schemas.team import TeamCreate, TeamResponse, PlayerCreate, PlayerResponse
from app.auth.jwt_handler import get_current_user

router = APIRouter()


@router.get("", response_model=list[TeamResponse])
def list_teams(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_team_to_response(t) for t in db.query(Team).filter(Team.user_id == user_id).all()]


@router.post("", response_model=TeamResponse)
def create_team(req: TeamCreate, user_id: int = Depends(get_current_user),
                db: Session = Depends(get_db)):
    team = Team(user_id=user_id, name=req.name)
    db.add(team); db.commit(); db.refresh(team)
    return _team_to_response(team)


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id: int, user_id: int = Depends(get_current_user),
             db: Session = Depends(get_db)):
    team = _get_team(db, team_id, user_id)
    return _team_to_response(team)


@router.delete("/{team_id}")
def delete_team(team_id: int, user_id: int = Depends(get_current_user),
                db: Session = Depends(get_db)):
    db.delete(_get_team(db, team_id, user_id)); db.commit()
    return {"ok": True}


@router.post("/{team_id}/players", response_model=PlayerResponse)
def add_player(team_id: int, req: PlayerCreate,
               user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_team(db, team_id, user_id)
    player = Player(team_id=team_id, name=req.name, number=req.number,
                    position=req.position, attributes=req.attributes)
    db.add(player); db.commit(); db.refresh(player)
    return _player_to_response(player)


@router.delete("/players/{player_id}")
def delete_player(player_id: int, user_id: int = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    player = db.query(Player).join(Team).filter(Player.id == player_id, Team.user_id == user_id).first()
    if not player: raise HTTPException(status_code=404)
    db.delete(player); db.commit()
    return {"ok": True}


def _get_team(db, team_id: int, user_id: int) -> Team:
    team = db.query(Team).filter(Team.id == team_id, Team.user_id == user_id).first()
    if not team: raise HTTPException(status_code=404)
    return team


def _team_to_response(t: Team) -> TeamResponse:
    return TeamResponse(id=t.id, user_id=t.user_id, name=t.name,
                        players=[_player_to_response(p) for p in (t.players or [])])


def _player_to_response(p: Player) -> PlayerResponse:
    return PlayerResponse(id=p.id, name=p.name, number=p.number,
                          position=p.position, attributes=p.attributes or {})
