"""Tactic endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tactic import Tactic
from app.schemas.tactics import TacticCreate, TacticUpdate, TacticResponse
from app.auth.jwt_handler import get_current_user

router = APIRouter()


@router.get("", response_model=list[TacticResponse])
def list_tactics(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_to_response(t) for t in db.query(Tactic).filter(Tactic.user_id == user_id).all()]


@router.post("", response_model=TacticResponse)
def create_tactic(req: TacticCreate, user_id: int = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    tactic = Tactic(user_id=user_id, **req.model_dump())
    db.add(tactic); db.commit(); db.refresh(tactic)
    return _to_response(tactic)


@router.get("/{tactic_id}", response_model=TacticResponse)
def get_tactic(tactic_id: int, user_id: int = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return _to_response(_get(db, tactic_id, user_id))


@router.put("/{tactic_id}", response_model=TacticResponse)
def update_tactic(tactic_id: int, req: TacticUpdate,
                  user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    tactic = _get(db, tactic_id, user_id)
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(tactic, key, value)
    db.commit(); db.refresh(tactic)
    return _to_response(tactic)


@router.delete("/{tactic_id}")
def delete_tactic(tactic_id: int, user_id: int = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    db.delete(_get(db, tactic_id, user_id)); db.commit()
    return {"ok": True}


def _get(db, tactic_id: int, user_id: int) -> Tactic:
    t = db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first()
    if not t: raise HTTPException(status_code=404)
    return t


def _to_response(t: Tactic) -> TacticResponse:
    return TacticResponse(
        id=t.id, user_id=t.user_id, team_id=t.team_id,
        name=t.name, formation=t.formation,
        player_positions=t.player_positions or {},
        pressing_level=t.pressing_level, defensive_line=t.defensive_line,
        attacking_width=t.attacking_width, tempo=t.tempo,
        passing_style=t.passing_style, build_up_style=t.build_up_style,
    )
