"""Replay file storage.

Dev:  local filesystem (./replays/)
Prod: Supabase Storage (1GB free, permanent)

Auto-selects based on SUPABASE_URL + SUPABASE_KEY env vars.
"""

from __future__ import annotations

import json
import gzip
import os
from pathlib import Path

import httpx


class LocalReplayStore:
    """Store replays as .jsonl.gz files on local disk."""

    def __init__(self, base_dir: str = "./replays"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, job_id: int, match_index: int, ticks: list[dict]) -> str:
        path = f"{job_id}/{match_index:04d}.jsonl.gz"
        full = self.base_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(full, "wt", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(t) for t in ticks))
        return path

    def load(self, job_id: int, match_index: int) -> list[dict]:
        full = self.base_dir / f"{job_id}/{match_index:04d}.jsonl.gz"
        if not full.exists():
            return []
        with gzip.open(full, "rt", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def url(self, path: str) -> str:
        return ""  # local dev — frontend fetches via API, not direct URL

    def delete_job(self, job_id: int):
        import shutil
        d = self.base_dir / str(job_id)
        if d.exists():
            shutil.rmtree(d)


class SupabaseReplayStore:
    """Store replays in Supabase Storage bucket."""

    BUCKET = "replays"

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self._ensure_bucket()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
        }

    def _ensure_bucket(self):
        """Create the replays bucket if it doesn't exist."""
        try:
            resp = httpx.get(
                f"{self.url}/storage/v1/bucket/{self.BUCKET}",
                headers=self._headers(),
            )
            if resp.status_code == 404:
                httpx.post(
                    f"{self.url}/storage/v1/bucket",
                    headers=self._headers(),
                    json={"name": self.BUCKET, "public": True},
                )
        except Exception:
            pass  # bucket creation is best-effort

    def save(self, job_id: int, match_index: int, ticks: list[dict]) -> str:
        path = f"{job_id}/{match_index:04d}.jsonl.gz"
        content = gzip.compress(
            "\n".join(json.dumps(t) for t in ticks).encode("utf-8")
        )
        resp = httpx.post(
            f"{self.url}/storage/v1/object/{self.BUCKET}/{path}",
            headers={**self._headers(), "Content-Type": "application/octet-stream"},
            content=content,
        )
        resp.raise_for_status()
        return path

    def load(self, job_id: int, match_index: int) -> list[dict]:
        path = f"{job_id}/{match_index:04d}.jsonl.gz"
        resp = httpx.get(
            f"{self.url}/storage/v1/object/{self.BUCKET}/{path}",
            headers=self._headers(),
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = gzip.decompress(resp.content).decode("utf-8")
        return [json.loads(line) for line in data.split("\n") if line.strip()]

    def url(self, path: str) -> str:
        """Public URL for direct access from frontend."""
        return f"{self.url}/storage/v1/object/public/{self.BUCKET}/{path}"

    def delete_job(self, job_id: int):
        # List and delete all files under job_id prefix
        resp = httpx.post(
            f"{self.url}/storage/v1/object/list/{self.BUCKET}",
            headers=self._headers(),
            json={"prefix": f"{job_id}/"},
        )
        if resp.status_code != 200:
            return
        files = resp.json()
        paths = [f"{job_id}/{f['name']}" for f in files]
        if paths:
            httpx.delete(
                f"{self.url}/storage/v1/object/{self.BUCKET}",
                headers=self._headers(),
                json={"prefixes": paths},
            )


def create_replay_store() -> LocalReplayStore | SupabaseReplayStore:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if url and key:
        return SupabaseReplayStore(url, key)
    return LocalReplayStore()


# Singleton
replay_store = create_replay_store()
