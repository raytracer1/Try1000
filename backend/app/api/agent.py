"""Agent endpoints — AI-powered tactics analysis and optimization."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tactic import Tactic
from app.models.simulation import SimulationJob, SimulationResult
from app.auth.jwt_handler import get_current_user
from app.config import settings

router = APIRouter()


@router.post("/tactics/analyze")
def analyze_tactic(tactic_id: str, user_id: str = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Request AI analysis of a tactic. Returns task status immediately."""
    tactic = db.query(Tactic).filter(
        Tactic.id == tactic_id, Tactic.user_id == user_id
    ).first()
    if not tactic:
        raise HTTPException(status_code=404)

    if not settings.llm_api_key:
        raise HTTPException(
            status_code=400,
            detail="No LLM API key configured. Add one in Settings to enable AI analysis."
        )

    # TODO: publish task via Ably for local agent to pick up
    # For now, return a placeholder — agent runs locally
    return {
        "status": "pending",
        "message": "Agent task created. Local agent will pick it up via Ably.",
        "tactic_id": tactic_id,
    }


@router.post("/match/report")
def generate_report(job_id: str, user_id: str = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Request AI match report for a simulation job."""
    job = db.query(SimulationJob).filter(
        SimulationJob.id == job_id, SimulationJob.user_id == user_id
    ).first()
    if not job:
        raise HTTPException(status_code=404)

    if not settings.llm_api_key:
        raise HTTPException(
            status_code=400,
            detail="No LLM API key configured."
        )

    return {
        "status": "pending",
        "message": "Report task created.",
        "job_id": job_id,
    }


@router.post("/tactics/optimize")
def optimize_tactic(tactic_id: str, job_id: str,
                    user_id: str = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Request AI optimization suggestions based on simulation results."""
    if not settings.llm_api_key:
        raise HTTPException(
            status_code=400,
            detail="No LLM API key configured."
        )

    return {
        "status": "pending",
        "message": "Optimization task created.",
        "tactic_id": tactic_id,
        "job_id": job_id,
    }
