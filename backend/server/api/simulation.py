"""Simulation endpoints."""

import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models.simulation import SimulationJob, SimulationResult
from server.schemas.simulation import (
    SimulateRequest, SimulateResponse, JobStatusResponse,
    JobDetailResponse, MatchResultResponse,
)
from server.auth.jwt_handler import get_current_user
from server.services.simulation_service import run_simulation_job
from server.services.ably_client import ably
from server.config import settings

router = APIRouter()

# Engine auth: simple API token check
def _engine_auth(request):
    token = request.headers.get("x-engine-token", "")
    if settings.ably_api_key and token != settings.ably_api_key:
        raise HTTPException(status_code=401, detail="Invalid engine token")
    return True


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

    # Notify local engine via Ably (falls back to thread if no Ably key)
    if settings.ably_api_key:
        ably.notify()
    else:
        threading.Thread(target=run_simulation_job, args=(job.id,), daemon=True).start()

    return SimulateResponse(job_id=job.id)


# ─── Engine-facing endpoints ───

@router.get("/engine/jobs/pending")
def engine_get_pending(_auth: bool = Depends(_engine_auth),
                       db: Session = Depends(get_db)):
    """Engine fetches ALL pending jobs. Ably is just a wake-up."""
    from server.models.team import Team, Player as PlayerModel
    from server.models.tactic import Tactic

    jobs = db.query(SimulationJob).filter(
        SimulationJob.status == "pending"
    ).order_by(SimulationJob.created_at.asc()).all()

    result = []
    for job in jobs:
        job.status = "running"
        home = db.query(Team).filter(Team.id == job.home_team_id).first()
        away = db.query(Team).filter(Team.id == job.away_team_id).first()
        home_tactic = db.query(Tactic).filter(Tactic.id == job.home_tactic_id).first()
        away_tactic = db.query(Tactic).filter(Tactic.id == job.away_tactic_id).first()

        result.append({
            "id": job.id, "match_count": job.match_count, "seed_base": job.seed_base,
            "home_players": _players_json(db, home),
            "away_players": _players_json(db, away),
            "home_tactic": _tactic_dict(home_tactic),
            "away_tactic": _tactic_dict(away_tactic),
        })

    db.commit()
    return {"jobs": result}


def _players_json(db, team) -> list:
    if not team: return []
    from server.models.team import Player as PlayerModel
    return [{"name": p.name, "number": p.number, "position": p.position,
             "attributes": p.attributes or {}}
            for p in db.query(PlayerModel).filter(PlayerModel.team_id == team.id).all()]


def _tactic_dict(t) -> dict:
    if not t: return {}
    return {"pressing_level": t.pressing_level, "defensive_line": t.defensive_line,
            "attacking_width": t.attacking_width, "tempo": t.tempo,
            "passing_style": t.passing_style, "build_up_style": t.build_up_style}


@router.post("/engine/jobs/{job_id}/result")
def engine_submit_result(job_id: int, result: dict,
                          _auth: bool = Depends(_engine_auth),
                          db: Session = Depends(get_db)):
    """Local engine submits a single match result."""
    from server.models.simulation import SimulationResult
    db.add(SimulationResult(
        job_id=job_id, match_index=result["match_index"],
        home_score=result["home_score"], away_score=result["away_score"],
        home_xg=result["home_xg"], away_xg=result["away_xg"],
        home_possession=result["home_possession"], away_possession=result["away_possession"],
        stats=result.get("stats", {}), replay_path=result.get("replay_path", ""),
    ))
    db.commit()
    return {"ok": True}


@router.put("/engine/jobs/{job_id}/complete")
def engine_complete_job(job_id: int, _auth: bool = Depends(_engine_auth),
                         db: Session = Depends(get_db)):
    """Local engine marks a job as completed."""
    from datetime import datetime
    job = db.query(SimulationJob).filter(SimulationJob.id == job_id).first()
    if job:
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


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

    from server.services.replay_store import replay_store
    ticks = replay_store.load(job_id, match_index)
    url = replay_store.url(f"{job_id}/{match_index:04d}.jsonl.gz") if hasattr(replay_store, "url") else ""

    return {"match_index": match_index, "ticks": ticks, "url": url}


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
