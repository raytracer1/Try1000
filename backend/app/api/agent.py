"""Agent endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tactic import Tactic
from app.models.simulation import SimulationJob
from app.auth.jwt_handler import get_current_user
from app.config import settings

router = APIRouter()


@router.post("/tactics/analyze")
def analyze_tactic(tactic_id: int, user_id: int = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if not db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first():
        raise HTTPException(status_code=404)
    if not settings.llm_api_key:
        raise HTTPException(status_code=400, detail="No LLM API key configured.")
    return {"status": "pending", "message": "Task created.", "tactic_id": tactic_id}


@router.post("/match/report")
def generate_report(job_id: int, user_id: int = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not db.query(SimulationJob).filter(SimulationJob.id == job_id, SimulationJob.user_id == user_id).first():
        raise HTTPException(status_code=404)
    if not settings.llm_api_key:
        raise HTTPException(status_code=400, detail="No LLM API key configured.")
    return {"status": "pending", "message": "Task created.", "job_id": job_id}


@router.post("/tactics/optimize")
def optimize_tactic(tactic_id: int, job_id: int,
                    user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.llm_api_key:
        raise HTTPException(status_code=400, detail="No LLM API key configured.")
    return {"status": "pending", "message": "Task created.", "tactic_id": tactic_id, "job_id": job_id}
