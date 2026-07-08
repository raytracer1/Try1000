"""Agent service — calls LLM directly using user's API key from their account."""

import json
import logging

logger = logging.getLogger(__name__)


def _llm_chat(provider: str, api_key: str, model: str, system: str, user: str) -> str:
    """Call LLM with user's key."""
    if not provider or not api_key:
        raise ValueError("User has not configured an LLM API key")

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=4096, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model, max_tokens=4096,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content


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


# ═══════════════════════════════════════════════════════════════
# Three agents
# ═══════════════════════════════════════════════════════════════

TACTICS_SYSTEM = """You are an expert football tactics analyst. Respond in JSON:
{"summary":"","style_label":"","strengths":[{"title":"","description":""}],"weaknesses":[{"title":"","description":""}],"ideal_against":"","vulnerable_against":""}
Be specific, grounded in the parameters. No clichés."""

REPORT_SYSTEM = """You are an expert football performance analyst. Respond in JSON:
{"headline":"","attack_analysis":{"effectiveness":"","patterns":[]},"possession_analysis":{"retention":"","transitions":""},"defensive_analysis":{"vulnerabilities":[],"pressing_effectiveness":""},"player_insights":[{"role":"","note":""}],"key_insight":""}"""

OPTIMIZE_SYSTEM = """You are an expert football tactics coach. Respond in JSON:
{"changes":[{"param":"","from":0,"to":0,"reason":""}],"expected_improvement":"","risk":""}
Max 3 changes. Each must reference data. Values within 1-10."""


def analyze_tactics(tactic: dict, llm_provider: str, llm_api_key: str, llm_model: str) -> dict:
    user_msg = f"Analyze this tactic:\n```json\n{json.dumps(tactic, indent=2)}\n```"
    return _parse(_llm_chat(llm_provider, llm_api_key, llm_model, TACTICS_SYSTEM, user_msg))


def generate_report(stats: dict, llm_provider: str, llm_api_key: str, llm_model: str) -> dict:
    user_msg = f"Simulation results (100 matches):\n```json\n{json.dumps(stats, indent=2)}\n```"
    return _parse(_llm_chat(llm_provider, llm_api_key, llm_model, REPORT_SYSTEM, user_msg))


def optimize_tactic(current: dict, stats: dict, llm_provider: str, llm_api_key: str, llm_model: str) -> dict:
    user_msg = f"Current tactic:\n```json\n{json.dumps(current, indent=2)}\n```\n\nResults:\n```json\n{json.dumps(stats, indent=2)}\n```"
    return _parse(_llm_chat(llm_provider, llm_api_key, llm_model, OPTIMIZE_SYSTEM, user_msg))
