"""Engine runner — subscribes to Ably, picks up simulation jobs, runs matches.

Usage:
    python -m try1000_engine.runner --ably-key=xxx --backend-url=https://api.try1000.io

Or poll-only (no Ably):
    python -m try1000_engine.runner --backend-url=http://localhost:8000 --poll
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import argparse
from datetime import datetime

logger = logging.getLogger(__name__)


class EngineRunner:
    """Runs on the user's machine. Picks up simulation tasks and executes them."""

    def __init__(self, backend_url: str, ably_key: str = ""):
        self.backend_url = backend_url.rstrip("/")
        self.ably_key = ably_key
        self._running = False

    def run(self, poll_interval: int = 5):
        """Main loop: poll for tasks and execute them."""
        logger.info(f"Engine runner started. Backend: {self.backend_url}")
        self._running = True

        if self.ably_key:
            self._subscribe_ably()
        else:
            logger.info("No Ably key — polling mode")
            self._poll_loop(poll_interval)

    def _subscribe_ably(self):
        """Subscribe to Ably for real-time task notifications."""
        try:
            from ably import AblyRest
            ably = AblyRest(self.ably_key)
            channel = ably.channels.get("try1000:tasks")

            def on_message(msg):
                data = json.loads(msg.data)
                logger.info(f"Received: {msg.name} job={data.get('job_id')}")
                if msg.name == "simulation_created":
                    self._handle_job(data["job_id"])

            channel.subscribe(on_message)
            logger.info("Subscribed to Ably — waiting for tasks...")
            while self._running:
                time.sleep(1)
        except ImportError:
            logger.error("ably-python not installed. Install with: pip install ably-python")
        except Exception as e:
            logger.error(f"Ably error: {e} — falling back to polling")
            self._poll_loop()

    def _poll_loop(self, interval: int = 5):
        """Poll the backend for pending jobs."""
        engine_token = self.ably_key or ""
        headers = {"x-engine-token": engine_token} if engine_token else {}

        while self._running:
            try:
                import httpx
                resp = httpx.get(
                    f"{self.backend_url}/api/v1/engine/jobs/next",
                    headers=headers, timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("job"):
                        self._handle_job(data["job"])
                    else:
                        time.sleep(interval)
                else:
                    time.sleep(interval)
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                time.sleep(interval)

    def _handle_job(self, job: dict | int):
        """Execute a simulation job and submit results."""
        if isinstance(job, int):
            # Fetch job details from backend
            job = self._fetch_job(job)
            if not job:
                return

        job_id = job["id"]
        match_count = job["match_count"]
        logger.info(f"Running job {job_id}: {match_count} matches")

        try:
            from try1000_engine.physics.player import Player as EnginePlayer
            from try1000_engine.ai.policy_factory import PolicyFactory
            from try1000_engine.match.match_engine import MatchEngine

            # Load data from backend
            home = self._load_players(job["home_team_id"], "home")
            away = self._load_players(job["away_team_id"], "away")
            home_tactic = self._load_tactic(job["home_tactic_id"])
            away_tactic = self._load_tactic(job["away_tactic_id"])

            # Policy: Level 1 (runner doesn't have LLM key)
            factory = PolicyFactory()
            home_policies = factory.create_team(home_tactic or {}, "Home")
            away_policies = factory.create_team(away_tactic or {}, "Away")

            engine_token = self.ably_key or ""

            for idx in range(match_count):
                engine = MatchEngine(
                    home_policies=home_policies, away_policies=away_policies,
                    seed=job["seed_base"] + idx,
                    record_replay=True,
                    fast_mode=(match_count > 10),
                    replay_sample_rate=1 if match_count <= 100 else 5,
                )
                result = engine.run(
                    [self._copy_player(p) for p in home],
                    [self._copy_player(p) for p in away],
                    match_index=idx,
                )

                # Save replay locally and submit
                replay_path = self._save_replay(job_id, idx, result.replay_ticks)
                self._submit_result(job_id, {
                    "match_index": idx,
                    "home_score": result.home_score, "away_score": result.away_score,
                    "home_xg": result.home_xg, "away_xg": result.away_xg,
                    "home_possession": result.home_possession,
                    "away_possession": result.away_possession,
                    "stats": result.to_dict(),
                    "replay_path": replay_path,
                }, engine_token)

                logger.info(f"Job {job_id} match {idx+1}/{match_count}: "
                            f"{result.home_score}-{result.away_score}")

            # Mark job complete
            import httpx
            httpx.put(
                f"{self.backend_url}/api/v1/engine/jobs/{job_id}/complete",
                headers={"x-engine-token": engine_token} if engine_token else {},
                timeout=10,
            )
            logger.info(f"Job {job_id} completed")

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")

    def _fetch_job(self, job_id: int) -> dict | None:
        import httpx
        try:
            resp = httpx.get(
                f"{self.backend_url}/api/v1/engine/jobs/next",
                timeout=10,
            )
            data = resp.json()
            return data.get("job")
        except Exception:
            return None

    def _load_players(self, team_id: int, team: str) -> list:
        import httpx
        resp = httpx.get(f"{self.backend_url}/api/v1/teams/{team_id}", timeout=10)
        data = resp.json()
        from try1000_engine.physics.player import Player as EnginePlayer
        players = []
        for i, p in enumerate(data.get("players", [])):
            a = p.get("attributes", {})
            players.append(EnginePlayer(
                player_id=f"{team}_{i+1}", team=team, role=p["position"],
                pace=a.get("pace", 70), shooting=a.get("shooting", 70),
                passing=a.get("passing", 70), dribbling=a.get("dribbling", 70),
                defending=a.get("defending", 70), physicality=a.get("physicality", 70),
                stamina_val=a.get("stamina", 100), awareness=a.get("awareness", 70),
                composure=a.get("composure", 70),
            ))
        return players

    def _load_tactic(self, tactic_id: int) -> dict | None:
        import httpx
        try:
            resp = httpx.get(f"{self.backend_url}/api/v1/tactics/{tactic_id}", timeout=10)
            t = resp.json()
            return {
                "pressing_level": t["pressing_level"],
                "defensive_line": t["defensive_line"],
                "attacking_width": t["attacking_width"],
                "tempo": t["tempo"],
                "passing_style": t["passing_style"],
                "build_up_style": t["build_up_style"],
            }
        except Exception:
            return {}

    def _save_replay(self, job_id: int, match_index: int, ticks: list[dict]) -> str:
        import gzip
        path = f"./replays/{job_id}/{match_index:04d}.jsonl.gz"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(t) for t in ticks))
        return path

    def _submit_result(self, job_id: int, result: dict, token: str):
        import httpx
        headers = {"x-engine-token": token} if token else {}
        httpx.post(
            f"{self.backend_url}/api/v1/engine/jobs/{job_id}/result",
            headers=headers, json=result, timeout=30,
        ).raise_for_status()

    def _copy_player(self, p):
        from try1000_engine.physics.player import Player as EnginePlayer
        return EnginePlayer(
            player_id=p.player_id, team=p.team, role=p.role,
            pace=p.pace, shooting=p.shooting, passing=p.passing,
            dribbling=p.dribbling, defending=p.defending,
            physicality=p.physicality, stamina_val=p.stamina,
            awareness=p.awareness, composure=p.composure,
        )


def main():
    parser = argparse.ArgumentParser(description="Try1000 Engine Runner")
    parser.add_argument("--backend-url",
                        default=os.environ.get("TRY1000_BACKEND_URL", "http://localhost:8000"),
                        help="Backend API URL (env: TRY1000_BACKEND_URL)")
    parser.add_argument("--ably-key",
                        default=os.environ.get("TRY1000_ABLY_KEY", ""),
                        help="Ably API key (env: TRY1000_ABLY_KEY)")
    parser.add_argument("--poll", action="store_true",
                        default=os.environ.get("TRY1000_POLL", "") == "1",
                        help="Poll mode without Ably (env: TRY1000_POLL=1)")
    parser.add_argument("--interval", type=int,
                        default=int(os.environ.get("TRY1000_POLL_INTERVAL", "5")),
                        help="Poll interval in seconds (env: TRY1000_POLL_INTERVAL)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    runner = EngineRunner(
        backend_url=args.backend_url,
        ably_key=args.ably_key,
    )
    runner.run(poll_interval=args.interval)


if __name__ == "__main__":
    main()
