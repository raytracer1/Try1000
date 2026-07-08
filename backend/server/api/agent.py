"""Agent endpoints — backend calls LLM directly with user's key."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.database import get_db
from server.models.tactic import Tactic
from server.models.simulation import SimulationJob, SimulationResult
from server.models.user import User
from server.models.agent import AgentResult
from server.auth.jwt_handler import get_current_user
from server.services.agent_service import analyze_tactics, generate_report, optimize_tactic

router = APIRouter()


def _save(db, user_id: int, task_type: str, result: dict,
          tactic_id: int | None = None, job_id: int | None = None):
    r = AgentResult(user_id=user_id, task_type=task_type,
                    tactic_id=tactic_id, job_id=job_id, result=result)
    db.add(r)
    db.commit()


def _get_llm(user: User) -> tuple[str, str, str]:
    if not user.llm_api_key or not user.llm_provider:
        raise HTTPException(status_code=400, detail="No LLM API key configured. Add one in Settings.")
    return user.llm_provider, user.llm_api_key, user.llm_model or "claude-sonnet-5"


def _summarize_results(results) -> dict:
    n = len(results)
    return {
        "match_count": n,
        "home_win_rate": round(sum(1 for r in results if r.home_score > r.away_score) / n, 3),
        "draw_rate": round(sum(1 for r in results if r.home_score == r.away_score) / n, 3),
        "avg_home_goals": round(sum(r.home_score for r in results) / n, 2),
        "avg_away_goals": round(sum(r.away_score for r in results) / n, 2),
        "avg_home_xg": round(sum(r.home_xg for r in results) / n, 4),
        "avg_away_xg": round(sum(r.away_xg for r in results) / n, 4),
        "avg_home_possession": round(sum(r.home_possession for r in results) / n, 1),
    }


@router.post("/tactics/analyze")
def analyze(tactic_id: int, user_id: int = Depends(get_current_user),
            db: Session = Depends(get_db)):
    tactic = db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first()
    if not tactic:
        raise HTTPException(status_code=404)

    user = db.query(User).filter(User.id == user_id).first()
    provider, key, model = _get_llm(user)

    result = analyze_tactics({
        "formation": tactic.formation,
        "pressing_level": tactic.pressing_level,
        "defensive_line": tactic.defensive_line,
        "attacking_width": tactic.attacking_width,
        "tempo": tactic.tempo,
        "passing_style": tactic.passing_style,
        "build_up_style": tactic.build_up_style,
    }, provider, key, model)
    _save(db, user_id, "analyze_tactics", result, tactic_id=tactic_id)
    return {"result": result}


@router.post("/match/report")
def report(job_id: int, user_id: int = Depends(get_current_user),
           db: Session = Depends(get_db)):
    job = db.query(SimulationJob).filter(
        SimulationJob.id == job_id, SimulationJob.user_id == user_id).first()
    if not job:
        raise HTTPException(status_code=404)

    results = db.query(SimulationResult).filter(
        SimulationResult.job_id == job_id).order_by(SimulationResult.match_index).all()
    if not results:
        raise HTTPException(status_code=400, detail="No results yet.")

    user = db.query(User).filter(User.id == user_id).first()
    provider, key, model = _get_llm(user)

    result = generate_report(_summarize_results(results), provider, key, model)
    _save(db, user_id, "match_report", result, job_id=job_id)
    return {"result": result}


@router.post("/tactics/optimize")
def optimize(tactic_id: int, job_id: int,
             user_id: int = Depends(get_current_user),
             db: Session = Depends(get_db)):
    tactic = db.query(Tactic).filter(Tactic.id == tactic_id, Tactic.user_id == user_id).first()
    if not tactic:
        raise HTTPException(status_code=404)

    results = db.query(SimulationResult).filter(
        SimulationResult.job_id == job_id).order_by(SimulationResult.match_index).all()
    if not results:
        raise HTTPException(status_code=400, detail="No results yet.")

    user = db.query(User).filter(User.id == user_id).first()
    provider, key, model = _get_llm(user)

    result = optimize_tactic({
        "formation": tactic.formation,
        "pressing_level": tactic.pressing_level,
        "defensive_line": tactic.defensive_line,
        "attacking_width": tactic.attacking_width,
        "tempo": tactic.tempo,
        "passing_style": tactic.passing_style,
        "build_up_style": tactic.build_up_style,
    }, _summarize_results(results), provider, key, model)
    _save(db, user_id, "optimize", result, tactic_id=tactic_id, job_id=job_id)
    return {"result": result}

@router.get("/results")
def get_results(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all agent results for the user."""
    results = db.query(AgentResult).filter(AgentResult.user_id == user_id)\
        .order_by(AgentResult.created_at.desc()).limit(20).all()
    return [{"id": r.id, "task_type": r.task_type, "result": r.result,
             "tactic_id": r.tactic_id, "job_id": r.job_id,
             "created_at": r.created_at.isoformat()} for r in results]

