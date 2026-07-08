"""Simulation service — runs engine jobs and stores results."""

import sys
import os
import logging
from datetime import datetime

# Add engine to path
ENGINE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "engine")
if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

logger = logging.getLogger(__name__)


def run_simulation_job(job_id: str):
    """Run a simulation job in the background. Called from a thread.

    This is the bridge between the backend and the engine:
    1. Load job + tactic + team data from DB
    2. Convert to engine Player objects
    3. Create Policy (Level 1 or Level 2 based on config)
    4. Run matches
    5. Save results to DB
    """
    from app.database import SessionLocal
    from app.models.simulation import SimulationJob, SimulationResult
    from app.models.team import Player as PlayerModel
    from app.config import settings

    db = SessionLocal()
    try:
        job = db.query(SimulationJob).filter(SimulationJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Mark as running
        job.status = "running"
        job.progress = 0
        db.commit()

        # Load teams and convert to engine Player objects
        from try1000_engine.physics.player import Player as EnginePlayer

        home_players = _load_players(db, job.home_team_id)
        away_players = _load_players(db, job.away_team_id)

        if len(home_players) < 11 or len(away_players) < 11:
            job.status = "failed"
            db.commit()
            logger.error(f"Job {job_id}: teams must have at least 11 players each")
            return

        # Create policies — Level 1 or Level 2 based on API key
        from try1000_engine.ai.policy_factory import PolicyFactory

        if settings.llm_api_key:
            from try1000_engine.ai.llm_generator import AnthropicClient
            client = AnthropicClient(
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
            factory = PolicyFactory(llm_client=client)
        else:
            factory = PolicyFactory()  # Level 1 fallback

        # Load tactic for home team
        from app.models.tactic import Tactic
        home_tactic = db.query(Tactic).filter(Tactic.id == job.home_tactic_id).first()
        away_tactic = db.query(Tactic).filter(Tactic.id == job.away_tactic_id).first()

        home_tactic_dict = _tactic_to_dict(home_tactic)
        away_tactic_dict = _tactic_to_dict(away_tactic)

        home_policies = factory.create_team(home_tactic_dict, "Home")
        away_policies = factory.create_team(away_tactic_dict, "Away")

        # Build engine and run matches
        from try1000_engine.match.match_engine import MatchEngine

        for match_idx in range(job.match_count):
            engine = MatchEngine(
                home_policies=home_policies,
                away_policies=away_policies,
                seed=job.seed_base + match_idx,
                record_replay=(job.match_count <= 100),
                fast_mode=(job.match_count > 10),
            )

            result = engine.run(
                [_copy_player(p) for p in home_players],
                [_copy_player(p) for p in away_players],
                match_index=match_idx,
            )

            # Store result
            sim_result = SimulationResult(
                job_id=job_id,
                match_index=match_idx,
                home_score=result.home_score,
                away_score=result.away_score,
                home_xg=result.home_xg,
                away_xg=result.away_xg,
                home_possession=result.home_possession,
                away_possession=result.away_possession,
                stats=result.to_dict(),
                events=result.replay_ticks if job.match_count <= 100 else [],
            )
            db.add(sim_result)

            # Update progress
            progress = int((match_idx + 1) / job.match_count * 100)
            job.progress = progress
            db.commit()

            logger.info(f"Job {job_id}: match {match_idx + 1}/{job.match_count} "
                        f"({result.home_score}-{result.away_score})")

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Job {job_id} completed: {job.match_count} matches")

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        try:
            job.status = "failed"
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _load_players(db, team_id: str) -> list:
    """Load players from DB and convert to engine Player objects."""
    from app.models.team import Player as PlayerModel
    from try1000_engine.physics.player import Player as EnginePlayer

    players = db.query(PlayerModel).filter(PlayerModel.team_id == team_id).all()
    engine_players = []
    for i, p in enumerate(players):
        attrs = p.attributes or {}
        ep = EnginePlayer(
            player_id=f"{'home' if i < 11 else 'away'}_{i + 1}",
            team="home" if i < 11 else "away",  # fixed in the caller
            role=p.position,
            pace=attrs.get("pace", 70),
            shooting=attrs.get("shooting", 70),
            passing=attrs.get("passing", 70),
            dribbling=attrs.get("dribbling", 70),
            defending=attrs.get("defending", 70),
            physicality=attrs.get("physicality", 70),
            stamina_val=attrs.get("stamina", 100),
            awareness=attrs.get("awareness", 70),
            composure=attrs.get("composure", 70),
        )
        engine_players.append(ep)
    return engine_players


def _tactic_to_dict(tactic) -> dict:
    """Convert Tactic model to dict for PolicyFactory."""
    if tactic is None:
        return {}
    return {
        "pressing_level": tactic.pressing_level,
        "defensive_line": tactic.defensive_line,
        "attacking_width": tactic.attacking_width,
        "tempo": tactic.tempo,
        "passing_style": tactic.passing_style,
        "build_up_style": tactic.build_up_style,
    }


def _copy_player(p) -> object:
    """Create a fresh copy of an engine Player for a new match."""
    from try1000_engine.physics.player import Player as EnginePlayer
    return EnginePlayer(
        player_id=p.player_id, team=p.team, role=p.role,
        x=p.x, y=p.y,
        pace=p.pace, shooting=p.shooting, passing=p.passing,
        dribbling=p.dribbling, defending=p.defending,
        physicality=p.physicality, stamina_val=p.stamina,
        awareness=p.awareness, composure=p.composure,
    )
