"""Simulation service — runs engine jobs and stores results."""

import sys, os, logging
from datetime import datetime

ENGINE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "engine")
if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

logger = logging.getLogger(__name__)


def run_simulation_job(job_id: int):
    """Run a simulation job in the background."""
    from app.database import SessionLocal
    from app.models.simulation import SimulationJob, SimulationResult
    from app.config import settings

    db = SessionLocal()
    try:
        job = db.query(SimulationJob).filter(SimulationJob.id == job_id).first()
        if not job: return

        job.status = "running"; job.progress = 0; db.commit()

        from try1000_engine.physics.player import Player as EnginePlayer
        from try1000_engine.ai.policy_factory import PolicyFactory

        # Load players
        home_players = _load_players(db, job.home_team_id)
        away_players = _load_players(db, job.away_team_id)

        if len(home_players) < 11 or len(away_players) < 11:
            job.status = "failed"; db.commit()
            logger.error(f"Job {job_id}: need 11 players per team"); return

        # Policy: Level 2 if API key set, else Level 1
        if settings.llm_api_key:
            from try1000_engine.ai.llm_generator import AnthropicClient
            factory = PolicyFactory(llm_client=AnthropicClient(api_key=settings.llm_api_key, model=settings.llm_model))
        else:
            factory = PolicyFactory()

        from app.models.tactic import Tactic
        home_tactic = db.query(Tactic).filter(Tactic.id == job.home_tactic_id).first()
        away_tactic = db.query(Tactic).filter(Tactic.id == job.away_tactic_id).first()
        home_policies = factory.create_team(_tactic_to_dict(home_tactic), "Home")
        away_policies = factory.create_team(_tactic_to_dict(away_tactic), "Away")

        from try1000_engine.match.match_engine import MatchEngine

        for idx in range(job.match_count):
            engine = MatchEngine(home_policies=home_policies, away_policies=away_policies,
                                 seed=job.seed_base + idx,
                                 record_replay=(job.match_count <= 100),
                                 fast_mode=(job.match_count > 10))
            result = engine.run([_copy(p) for p in home_players],
                                [_copy(p) for p in away_players], match_index=idx)

            db.add(SimulationResult(job_id=job_id, match_index=idx,
                                    home_score=result.home_score, away_score=result.away_score,
                                    home_xg=result.home_xg, away_xg=result.away_xg,
                                    home_possession=result.home_possession, away_possession=result.away_possession,
                                    stats=result.to_dict(),
                                    events=result.replay_ticks if job.match_count <= 100 else []))
            job.progress = int((idx + 1) / job.match_count * 100)
            db.commit()

        job.status = "completed"; job.completed_at = datetime.utcnow(); db.commit()
        logger.info(f"Job {job_id} done: {job.match_count} matches")

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        try: job.status = "failed"; db.commit()
        except: pass
    finally:
        db.close()


def _load_players(db, team_id: int) -> list:
    from app.models.team import Player as PlayerModel
    from try1000_engine.physics.player import Player as EnginePlayer
    players = db.query(PlayerModel).filter(PlayerModel.team_id == team_id).all()
    result = []
    for i, p in enumerate(players):
        a = p.attributes or {}
        result.append(EnginePlayer(player_id=f"t{team_id}_p{i+1}", team="home", role=p.position,
                                   pace=a.get("pace", 70), shooting=a.get("shooting", 70),
                                   passing=a.get("passing", 70), dribbling=a.get("dribbling", 70),
                                   defending=a.get("defending", 70), physicality=a.get("physicality", 70),
                                   stamina_val=a.get("stamina", 100), awareness=a.get("awareness", 70),
                                   composure=a.get("composure", 70)))
    return result


def _tactic_to_dict(tactic) -> dict:
    if not tactic: return {}
    return {"pressing_level": tactic.pressing_level, "defensive_line": tactic.defensive_line,
            "attacking_width": tactic.attacking_width, "tempo": tactic.tempo,
            "passing_style": tactic.passing_style, "build_up_style": tactic.build_up_style}


def _copy(p):
    from try1000_engine.physics.player import Player as EnginePlayer
    return EnginePlayer(player_id=p.player_id, team=p.team, role=p.role, x=p.x, y=p.y,
                        pace=p.pace, shooting=p.shooting, passing=p.passing,
                        dribbling=p.dribbling, defending=p.defending,
                        physicality=p.physicality, stamina_val=p.stamina,
                        awareness=p.awareness, composure=p.composure)
