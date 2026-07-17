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
import threading
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class EngineRunner:
    """Runs on the user's machine. Picks up simulation tasks and executes them."""

    def __init__(self, backend_url: str, ably_key: str = "", max_workers: int = 4):
        self.backend_url = backend_url.rstrip("/")
        self.ably_key = ably_key
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_jobs: set[int] = set()
        self._lock = threading.Lock()

    def run(self, poll_interval: int = 5):
        """Main loop: Ably for real-time + polling as safety net.

        Ably is the fast path. Polling catches any messages that
        were missed due to network issues or engine restart.
        """
        logger.info(f"Engine runner started. Backend: {self.backend_url}")
        self._running = True

        # Always run poll as safety net
        poll_thread = threading.Thread(target=self._poll_loop, args=(poll_interval,), daemon=True)
        poll_thread.start()

        if self.ably_key:
            self._subscribe_ably()  # blocks on Ably subscription
        else:
            logger.info("No Ably key — polling mode only")
            poll_thread.join()  # wait forever on poll

    def _subscribe_ably(self):
        """Subscribe to Ably for real-time task notifications."""
        import asyncio

        async def listen(runner):
            try:
                from ably import AblyRealtime
                ably = AblyRealtime(runner.ably_key)
                channel = ably.channels.get("try1000:tasks")

                async def on_message(msg):
                    logger.info("Ably wakeup received")
                    runner._fetch_and_dispatch()

                await channel.subscribe(on_message)
                logger.info("Subscribed to Ably — waiting for tasks...")
                while runner._running:
                    await asyncio.sleep(1)
            except ImportError:
                logger.error("ably-python not installed. Install with: pip install ably-python")
            except Exception as e:
                logger.error(f"Ably error: {e} — falling back to polling")

        try:
            asyncio.run(listen(self))
        except RuntimeError:
            # Already-running event loop — run in a dedicated thread
            t = threading.Thread(target=lambda: asyncio.run(listen(self)), daemon=True)
            t.start()
            self._poll_loop()

    def _poll_loop(self, initial_interval: int = 5, max_interval: int = 1800):
        """Poll the backend for pending jobs with exponential backoff as safety net.
        Interval doubles each poll up to max_interval. Resets to initial_interval
        when a job is found (indicating Ably may have missed something)."""
        interval = initial_interval
        while self._running:
            try:
                found = self._fetch_and_dispatch()
                if found:
                    logger.info(f"Poll found {found} job(s) — resetting interval to {initial_interval}s")
                    interval = initial_interval
                else:
                    old = interval
                    interval = min(interval * 2, max_interval)
                    if old != interval:
                        logger.info(f"Poll backoff: {old}s → {interval}s")
            except Exception as e:
                logger.warning(f"Poll error: {e}")
            time.sleep(interval)

    def _fetch_and_dispatch(self):
        """Fetch all pending jobs from backend and dispatch each to a worker.
        Returns the number of jobs found. Retries up to 3 times on failure."""
        import httpx
        engine_token = self.ably_key or ""
        headers = {"x-engine-token": engine_token} if engine_token else {}

        for attempt in range(3):
            try:
                resp = httpx.get(
                    f"{self.backend_url}/api/v1/engine/jobs/pending",
                    headers=headers, timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    for job in jobs:
                        self._dispatch_job(job)
                    return len(jobs)
                if attempt < 2:
                    delay = (attempt + 1) * 2
                    logger.warning(f"Pending jobs returned {resp.status_code}, retry {attempt+1}/3 in {delay}s")
                    time.sleep(delay)
            except Exception as e:
                if attempt < 2:
                    delay = (attempt + 1) * 2
                    logger.warning(f"Failed to fetch pending jobs: {e}, retry {attempt+1}/3 in {delay}s")
                    time.sleep(delay)
        return 0

    def _dispatch_job(self, job: dict):
        """Submit job to thread pool if not already running."""
        job_id = job["id"]
        with self._lock:
            if job_id in self._active_jobs:
                return
            self._active_jobs.add(job_id)

        self._executor.submit(self._handle, job_id, job)

    def _handle(self, job_id: int, job: dict):
        """Run a job and clean up when done."""
        try:
            self._handle_job(job)
        finally:
            with self._lock:
                self._active_jobs.discard(job_id)

    def _handle_job(self, job: dict):
        """Execute a simulation job and submit results. Job dict has all data."""
        job_id = job["id"]
        match_count = job["match_count"]
        logger.info(f"Running job {job_id}: {match_count} matches")

        try:
            from try1000_engine.physics.player import Player as EnginePlayer
            from try1000_engine.ai.policy_factory import PolicyFactory
            from try1000_engine.match.match_engine import MatchEngine

            # Players and tactics come from the job detail endpoint
            home = self._parse_players(job.get("home_players", []), "home")
            away = self._parse_players(job.get("away_players", []), "away")
            home_tactic = job.get("home_tactic", {})
            away_tactic = job.get("away_tactic", {})

            # Policy: Level 2 if user has LLM key, else Level 1
            llm_provider = job.get("llm_provider")
            llm_api_key = job.get("llm_api_key")
            llm_model = job.get("llm_model", "claude-sonnet-5")
            if llm_provider and llm_api_key:
                if llm_provider == "anthropic":
                    from try1000_engine.ai.llm_generator import AnthropicClient
                    factory = PolicyFactory(llm_client=AnthropicClient(api_key=llm_api_key, model=llm_model))
                else:
                    from try1000_engine.ai.llm_generator import OpenAICompatibleClient
                    factory = PolicyFactory(llm_client=OpenAICompatibleClient(api_key=llm_api_key, model=llm_model))
            else:
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

    def _parse_players(self, players_json: list[dict], team: str) -> list:
        from try1000_engine.physics.player import Player as EnginePlayer
        result = []
        for i, p in enumerate(players_json):
            a = p.get("attributes", {})
            result.append(EnginePlayer(
                player_id=f"{team}_{i+1}", team=team, role=p["position"],
                pace=a.get("pace", 70), shooting=a.get("shooting", 70),
                passing=a.get("passing", 70), dribbling=a.get("dribbling", 70),
                defending=a.get("defending", 70), physicality=a.get("physicality", 70),
                stamina_val=a.get("stamina", 100), awareness=a.get("awareness", 70),
                composure=a.get("composure", 70),
            ))
        return result

    def _save_replay(self, job_id: int, match_index: int, ticks: list[dict]) -> str:
        import gzip, io
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

        # Compress replay data in memory
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write("\n".join(json.dumps(t) for t in ticks).encode("utf-8"))
        compressed = buf.getvalue()

        # Upload to Supabase Storage if configured
        if supabase_url and supabase_key:
            try:
                from supabase import create_client, Client
                supabase: Client = create_client(supabase_url, supabase_key)
                # Ensure the bucket exists
                try:
                    buckets = supabase.storage.list_buckets()
                    if not any(b.name == "replays" for b in buckets):
                        supabase.storage.create_bucket("replays", options={"public": False})
                except Exception:
                    pass  # bucket may already exist
                storage_path = f"{job_id}/{match_index:04d}.jsonl.gz"
                supabase.storage.from_("replays").upload(
                    path=storage_path,
                    file=compressed,
                    file_options={"content-type": "application/gzip", "upsert": "true"},
                )
                return f"supabase://replays/{storage_path}"
            except Exception as e:
                logger.warning(f"Supabase upload failed, falling back to local: {e}")

        # Fallback: save to local disk
        path = f"./replays/{job_id}/{match_index:04d}.jsonl.gz"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(compressed)
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
    parser.add_argument("--workers", type=int,
                        default=int(os.environ.get("TRY1000_WORKERS", "4")),
                        help="Max concurrent jobs (env: TRY1000_WORKERS)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    runner = EngineRunner(
        backend_url=args.backend_url,
        ably_key=args.ably_key,
    )
    runner.run(poll_interval=args.interval)


if __name__ == "__main__":
    main()
