"""Tactic endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tactic import Tactic
from app.schemas.tactics import TacticCreate, TacticUpdate, TacticResponse
from app.auth.jwt_handler import get_current_user

router = APIRouter()


@router.get("", response_model=list[TacticResponse])
def list_tactics(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    tactics = db.query(Tactic).filter(Tactic.user_id == user_id).all()
    return [_tactic_to_response(t) for t in tactics]


@router.post("", response_model=TacticResponse)
def create_tactic(req: TacticCreate, user_id: str = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    tactic = Tactic(user_id=user_id, **req.model_dump())
    db.add(tactic)
    db.commit()
    db.refresh(tactic)
    return _tactic_to_response(tactic)


@router.get("/{tactic_id}", response_model=TacticResponse)
def get_tactic(tactic_id: str, user_id: str = Depends(get_current_user),
               db: Session = Depends(get_db)):
    tactic = db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first()
    if not tactic:
        raise HTTPException(status_code=404)
    return _tactic_to_response(tactic)


@router.put("/{tactic_id}", response_model=TacticResponse)
def update_tactic(tactic_id: str, req: TacticUpdate,
                  user_id: str = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    tactic = db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first()
    if not tactic:
        raise HTTPException(status_code=404)

    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(tactic, key, value)

    db.commit()
    db.refresh(tactic)
    return _tactic_to_response(tactic)


@router.delete("/{tactic_id}")
def delete_tactic(tactic_id: str, user_id: str = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    tactic = db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first()
    if not tactic:
        raise HTTPException(status_code=404)
    db.delete(tactic)
    db.commit()
    return {"ok": True}


def _tactic_to_response(t: Tactic) -> TacticResponse:
    return TacticResponse(
        id=str(t.id), user_id=str(t.user_id), team_id=str(t.team_id),
        name=t.name, formation=t.formation,
        player_positions=t.player_positions or {},
        pressing_level=t.pressing_level, defensive_line=t.defensive_line,
        attacking_width=t.attacking_width, tempo=t.tempo,
        passing_style=t.passing_style, build_up_style=t.build_up_style,
    )
