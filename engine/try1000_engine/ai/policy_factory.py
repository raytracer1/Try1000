"""PolicyFactory — auto-selects Level 2 (LLM) or Level 1 (rule-based).

Default: use LLM-generated GeneratedPolicy.
Fallback: when no API key is configured, use RuleBasedPolicy.

Also caches generated policies by (role, tactic_hash) so the LLM
is only called once per role+tactic combination.
"""

from __future__ import annotations

import hashlib
import json
import logging

from try1000_engine.ai.policy import Policy
from try1000_engine.ai.rule_based import RuleBasedPolicy
from try1000_engine.ai.generated_policy import GeneratedPolicy
from try1000_engine.ai.llm_generator import CodeGenerator, LLMClient

logger = logging.getLogger(__name__)


class PolicyFactory:
    """Creates per-role Policy instances for a team.

    Auto-selects implementation:
    - LLM client available → Level 2 (LLM-generated code)
    - No LLM client → Level 1 (rule-based, no API needed)

    Usage:
        # Level 2 (default, needs API key)
        client = AnthropicClient(api_key="sk-...")
        factory = PolicyFactory(llm_client=client)
        policies = factory.create_team(tactic={"pressing_level": 7, ...})
        engine = MatchEngine(policies["home"], policies["away"])

        # Level 1 (fallback, no API key)
        factory = PolicyFactory()  # no client
        policies = factory.create_team(tactic={...})  # uses RuleBasedPolicy
    """

    # Roles that need distinct generated code (mirrors get unique code)
    UNIQUE_ROLES = ["GK", "CB", "LB", "CDM", "CM", "CAM", "LW", "ST"]

    # Map all 11 positions to their code-generating role
    ROLE_MAP = {
        "GK": "GK",
        "CB": "CB",
        "LB": "LB", "RB": "LB",
        "CDM": "CDM",
        "CM": "CM",
        "CAM": "CAM",
        "LM": "LW", "RM": "LW", "LW": "LW", "RW": "LW",
        "ST": "ST",
    }

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client
        self._cache: dict[str, GeneratedPolicy] = {}  # key → policy

    @property
    def is_level2(self) -> bool:
        """Whether Level 2 (LLM-generated) is active."""
        return self.llm_client is not None

    def create_team(self, tactic: dict | None = None,
                    team_name: str = "Team") -> dict[str, Policy]:
        """Create per-role policies for all 11 positions.

        Returns dict keyed by role name (e.g. {"ST": policy, "CB": policy, ...}).
        """
        tactic = tactic or {}
        team_name = team_name or "Team"

        if self.llm_client is None:
            logger.info("No LLM client configured — using RuleBasedPolicy (Level 1)")
            return self._rule_based_team(tactic)

        try:
            logger.info("LLM client available — using GeneratedPolicy (Level 2)")
            return self._generated_team(tactic, team_name)
        except Exception as e:
            logger.warning(
                f"LLM code generation failed ({e}). "
                "Falling back to RuleBasedPolicy (Level 1)."
            )
            return self._rule_based_team(tactic)

    def create_policy(self, role: str, tactic: dict | None = None,
                      team_name: str = "Team") -> Policy:
        """Create a policy for a single role."""
        if self.llm_client is None:
            return RuleBasedPolicy(tactic)

        base_role = self.ROLE_MAP.get(role, "CM")
        cache_key = self._cache_key(base_role, tactic)

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            generator = CodeGenerator(self.llm_client)
            code = generator.generate(base_role, tactic, team_name)
            policy = GeneratedPolicy(code=code, role=base_role, tactic=tactic)
            self._cache[cache_key] = policy
            return policy
        except Exception:
            return RuleBasedPolicy(tactic)

    def clear_cache(self):
        """Clear the generated code cache (forces regeneration on next use)."""
        self._cache.clear()

    # ─── Internal ───

    def _generated_team(self, tactic: dict, team_name: str) -> dict[str, Policy]:
        """Generate LLM code for each unique role, then map to all 11 positions."""
        generator = CodeGenerator(self.llm_client)

        # Generate for unique roles only
        role_codes = {}
        for role in self.UNIQUE_ROLES:
            cache_key = self._cache_key(role, tactic)
            if cache_key in self._cache:
                role_codes[role] = self._cache[cache_key].code
            else:
                code = generator.generate(role, tactic, team_name)
                role_codes[role] = code

        # Build policies for all 11 positions
        policies = {}
        for position, base_role in self.ROLE_MAP.items():
            code = role_codes.get(base_role, role_codes.get("CM", ""))
            cache_key = self._cache_key(position, tactic)
            if cache_key not in self._cache:
                policy = GeneratedPolicy(code=code, role=position, tactic=tactic)
                self._cache[cache_key] = policy
            policies[position] = self._cache[cache_key]

        return policies

    def _rule_based_team(self, tactic: dict) -> dict[str, Policy]:
        """Create RuleBasedPolicy for all 11 positions."""
        return {role: RuleBasedPolicy(tactic) for role in self.ROLE_MAP}

    def _cache_key(self, role: str, tactic: dict) -> str:
        """Stable cache key for a role+tactic combination."""
        data = json.dumps({"role": role, "tactic": tactic}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
