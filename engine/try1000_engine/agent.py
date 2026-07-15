"""Agent — runs locally, calls Qwen via DashScope API.

LLM API key from TRY1000_LLM_API_KEY env var.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

DASHSCOPE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen-plus"


def _call_qwen(system: str, user: str, api_key: str = "", model: str = MODEL) -> str:
    key = api_key or os.environ.get("TRY1000_LLM_API_KEY", "")
    if not key:
        raise RuntimeError("Set TRY1000_LLM_API_KEY")

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 4096,
    }).encode("utf-8")

    req = Request(DASHSCOPE_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    })

    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except URLError as e:
        raise RuntimeError(f"Qwen API error: {e}")


TACTICS_SYSTEM = """You are an expert football tactics analyst. Respond in JSON:
{"summary":"","style_label":"","strengths":[{"title":"","description":""}],"weaknesses":[{"title":"","description":""}],"ideal_against":"","vulnerable_against":""}
Be specific, grounded in the parameters. No clichés."""

REPORT_SYSTEM = """You are an expert football performance analyst. Respond in JSON:
{"headline":"","attack_analysis":{"effectiveness":"","patterns":[]},"possession_analysis":{"retention":"","transitions":""},"defensive_analysis":{"vulnerabilities":[],"pressing_effectiveness":""},"player_insights":[{"role":"","note":""}],"key_insight":""}"""

OPTIMIZE_SYSTEM = """You are an expert football tactics coach. Respond in JSON:
{"changes":[{"param":"","from":0,"to":0,"reason":""}],"expected_improvement":"","risk":""}
Max 3 changes. Each must reference data. Values within 1-10."""


def analyze_tactics(tactic: dict) -> dict:
    user = f"Analyze this tactic:\n```json\n{json.dumps(tactic, indent=2)}\n```"
    return _parse(_call_qwen(TACTICS_SYSTEM, user))


def generate_report(stats: dict) -> dict:
    user = f"Simulation results:\n```json\n{json.dumps(stats, indent=2)}\n```"
    return _parse(_call_qwen(REPORT_SYSTEM, user))


def optimize_tactic(current: dict, stats: dict) -> dict:
    user = f"Current tactic:\n```json\n{json.dumps(current, indent=2)}\n```\n\nResults:\n```json\n{json.dumps(stats, indent=2)}\n```"
    return _parse(_call_qwen(OPTIMIZE_SYSTEM, user))


def _parse(text: str) -> dict:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "raw": text[:500]}
