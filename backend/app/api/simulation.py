"""Simulation endpoints."""

import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.simulation import SimulationJob, SimulationResult
from app.schemas.simulation import (
    SimulateRequest, SimulateResponse, JobStatusResponse,
    JobDetailResponse, MatchResultResponse,
)
from app.auth.jwt_handler import get_current_user
from app.services.simulation_service import run_simulation_job

router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
def start_simulation(req: SimulateRequest, user_id: int = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if req.match_count not in (1, 10, 100, 1000):
        raise HTTPException(status_code=400, detail="match_count must be 1, 10, 100, or 1000")

    job = SimulationJob(user_id=user_id, home_team_id=req.home_team_id,
                        away_team_id=req.away_team_id, home_tactic_id=req.home_tactic_id,
                        away_tactic_id=req.away_tactic_id, match_count=req.match_count,
                        status="pending")
    db.add(job); db.commit(); db.refresh(job)

    threading.Thread(target=run_simulation_job, args=(job.id,), daemon=True).start()
    return SimulateResponse(job_id=job.id)


@router.get("/simulation/jobs", response_model=list[JobStatusResponse])
def list_jobs(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = db.query(SimulationJob).filter(SimulationJob.user_id == user_id)\
        .order_by(SimulationJob.created_at.desc()).limit(20).all()
    return [_job_to_status(j) for j in jobs]


@router.get("/simulation/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: int, user_id: int = Depends(get_current_user),
            db: Session = Depends(get_db)):
    job = _get_job(db, job_id, user_id)
    results = db.query(SimulationResult).filter(SimulationResult.job_id == job_id)\
        .order_by(SimulationResult.match_index).all()
    return JobDetailResponse(**_job_to_status(job).model_dump(),
                             results=[_result_to_response(r) for r in results])


@router.get("/simulation/jobs/{job_id}/replay/{match_index}")
def get_replay(job_id: int, match_index: int,
               user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_job(db, job_id, user_id)
    result = db.query(SimulationResult).filter(
        SimulationResult.job_id == job_id, SimulationResult.match_index == match_index).first()
    if not result: raise HTTPException(status_code=404)
    return {"match_index": match_index, "ticks": result.events or []}


def _get_job(db, job_id: int, user_id: int) -> SimulationJob:
    job = db.query(SimulationJob).filter(SimulationJob.id == job_id, SimulationJob.user_id == user_id).first()
    if not job: raise HTTPException(status_code=404)
    return job


def _job_to_status(j: SimulationJob) -> JobStatusResponse:
    return JobStatusResponse(id=j.id, status=j.status, progress=j.progress,
                             match_count=j.match_count, home_team_id=j.home_team_id,
                             away_team_id=j.away_team_id,
                             created_at=j.created_at.isoformat() if j.created_at else "",
                             completed_at=j.completed_at.isoformat() if j.completed_at else None)


def _result_to_response(r: SimulationResult) -> MatchResultResponse:
    return MatchResultResponse(match_index=r.match_index, home_score=r.home_score,
                               away_score=r.away_score, home_xg=r.home_xg, away_xg=r.away_xg,
                               home_possession=r.home_possession, away_possession=r.away_possession,
                               stats=r.stats or {})
