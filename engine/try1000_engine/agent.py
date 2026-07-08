"""Agent — runs locally, calls LLM with user's API key.

Three agents:
1. TacticsAgent — explain strengths/weaknesses of a tactic
2. AnalysisAgent — generate tactical report from simulation stats
3. OptimizationAgent — suggest parameter changes based on results

LLM API key comes from environment (TRY1000_LLM_API_KEY), never sent to backend.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


class AgentLLM:
    """LLM client — key comes from user account via backend, not env vars."""

    def __init__(self, provider: str = "", api_key: str = "", model: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.model = model or "claude-sonnet-5"

    def available(self) -> bool:
        return bool(self.api_key and self.provider)

    def chat(self, system: str, user: str) -> str:
        if self.provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model=self.model, max_tokens=4096, system=system,
                messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text

        elif self.provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model, max_tokens=4096,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            return resp.choices[0].message.content

        else:
            raise RuntimeError("Set TRY1000_LLM_PROVIDER and TRY1000_LLM_API_KEY")


# ═══════════════════════════════════════════════════════════════
# Prompt templates
# ═══════════════════════════════════════════════════════════════

TACTICS_SYSTEM = """You are an expert football tactics analyst. Respond in JSON:
{
  "summary": "one sentence",
  "style_label": "e.g. High-Press Possession",
  "strengths": [{"title": "", "description": ""}],
  "weaknesses": [{"title": "", "description": ""}],
  "ideal_against": "what this counters",
  "vulnerable_against": "what counters this"
}
Be specific, grounded in the parameters. No clichés."""

REPORT_SYSTEM = """You are an expert football performance analyst. Respond in JSON:
{
  "headline": "one-line summary",
  "attack_analysis": {"effectiveness": "", "patterns": []},
  "possession_analysis": {"retention": "", "transitions": ""},
  "defensive_analysis": {"vulnerabilities": [], "pressing_effectiveness": ""},
  "player_insights": [{"role": "", "note": ""}],
  "key_insight": "the single most important finding"
}"""

OPTIMIZE_SYSTEM = """You are an expert football tactics coach. Respond in JSON:
{
  "changes": [{"param": "", "from": 0, "to": 0, "reason": ""}],
  "expected_improvement": "",
  "risk": ""
}
Max 3 changes. Each must reference data. Values within 1-10."""


# ═══════════════════════════════════════════════════════════════
# Agent functions
# ═══════════════════════════════════════════════════════════════

def _make_llm(task: dict) -> AgentLLM:
    return AgentLLM(
        provider=task.get("llm_provider", ""),
        api_key=task.get("llm_api_key", ""),
        model=task.get("llm_model", ""),
    )


def run_task(task: dict) -> dict:
    """Execute a single agent task. Returns result dict."""
    task_type = task["task_type"]
    llm = _make_llm(task)

    if not llm.available():
        return {"error": "User has not configured an LLM API key"}

    try:
        if task_type == "analyze_tactics":
            user = f"Analyze this tactic:\n```json\n{json.dumps(task.get('tactic', {}), indent=2)}\n```"
            return _parse(llm.chat(TACTICS_SYSTEM, user))

        elif task_type == "match_report":
            user = f"Simulation results:\n```json\n{json.dumps(task.get('stats', {}), indent=2)}\n```"
            return _parse(llm.chat(REPORT_SYSTEM, user))

        elif task_type == "optimize":
            user = f"Current tactic:\n```json\n{json.dumps(task.get('tactic', {}), indent=2)}\n```\n\nResults:\n```json\n{json.dumps(task.get('stats', {}), indent=2)}\n```"
            return _parse(llm.chat(OPTIMIZE_SYSTEM, user))

        else:
            return {"error": f"Unknown task type: {task_type}"}
    except Exception as e:
        logger.exception(f"Agent task {task.get('id')} failed")
        return {"error": str(e)}


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
