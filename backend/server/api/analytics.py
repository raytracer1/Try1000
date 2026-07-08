"""Analytics endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models.simulation import SimulationJob, SimulationResult
from server.auth.jwt_handler import get_current_user

router = APIRouter()


@router.get("/job/{job_id}")
def get_job_analytics(job_id: int, user_id: int = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    job = db.query(SimulationJob).filter(SimulationJob.id == job_id, SimulationJob.user_id == user_id).first()
    if not job: raise HTTPException(status_code=404)

    results = db.query(SimulationResult).filter(SimulationResult.job_id == job_id)\
        .order_by(SimulationResult.match_index).all()
    if not results: return {"job_id": job_id, "match_count": 0, "message": "No results yet"}

    n = len(results)
    return {
        "job_id": job_id, "match_count": n,
        "home_win_rate": round(sum(1 for r in results if r.home_score > r.away_score) / n, 3),
        "draw_rate": round(sum(1 for r in results if r.home_score == r.away_score) / n, 3),
        "away_win_rate": round(sum(1 for r in results if r.away_score > r.home_score) / n, 3),
        "avg_home_goals": round(sum(r.home_score for r in results) / n, 2),
        "avg_away_goals": round(sum(r.away_score for r in results) / n, 2),
        "avg_home_xg": round(sum(r.home_xg for r in results) / n, 4),
        "avg_away_xg": round(sum(r.away_xg for r in results) / n, 4),
        "avg_home_possession": round(sum(r.home_possession for r in results) / n, 1),
    }


@router.get("/job/{job_id}/match/{match_index}")
def get_match_analytics(job_id: int, match_index: int,
                        user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    result = db.query(SimulationResult).filter(
        SimulationResult.job_id == job_id, SimulationResult.match_index == match_index).first()
    if not result: raise HTTPException(status_code=404)
    return {"match_index": match_index, "home_score": result.home_score,
            "away_score": result.away_score, "home_xg": result.home_xg,
            "away_xg": result.away_xg, "home_possession": result.home_possession,
            "away_possession": result.away_possession, "stats": result.stats or {},
            "event_count": len(result.events or [])}
