"""
Eir Router — Effort and Model Routing
======================================
Determines how much effort to spend and which model to use
for each task, based on conditions and configured profiles.

Like the Norns at the Well of Urðr, the router reads the threads
of the past (system state) to determine what the present requires.
"""

import logging
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .layers import (
    CHECK_REGISTRY,
    EffortLevel,
    EffortProfile,
    QUICK_PROFILE,
    STANDARD_PROFILE,
    DEEP_PROFILE,
    EMERGENCY_PROFILE,
    get_profile,
    load_profiles_from_yaml,
    merge_profiles,
    PROFILES,
    TaskComplexity,
)

logger = logging.getLogger("eir.router")


# ─── Model Selection ──────────────────────────────────────────────────────

MODEL_TIERS = {
    "lightweight": {  # Fast, cheap, good enough for diagnostics & simple tasks
        "models": ["glm-4", "deepseek-v4-flash"],
        "max_tokens": 500,
        "priority": 3,
    },
    "midweight": {  # Balanced — semantic matching, pattern recognition
        "models": ["glm-5.1", "deepseek-v4-pro", "qwen3.5-plus"],
        "max_tokens": 2000,
        "priority": 2,
    },
    "heavyweight": {  # Best available — complex reasoning, judgment calls
        "models": ["deepseek-v4-pro", "glm-5.1"],
        "max_tokens": 4000,
        "priority": 1,
    },
}

# Map task complexities to model tiers
COMPLEXITY_TO_TIER = {
    TaskComplexity.DIAGNOSTIC: "lightweight",
    TaskComplexity.SEMANTIC: "midweight",
    TaskComplexity.REASONING: "midweight",
    TaskComplexity.COMPLEX: "heavyweight",
}


class EffortRouter:
    """Routes effort level based on system conditions.
    
    Conditions examined:
    - Time since last deep check (urge deep if overdue)
    - Number of known errors/blockers (escalate if many)
    - Disk pressure (stay quick if low, run standard if medium)
    - Manual override (cron jobs can specify directly)
    
    Like the völva reading the threads, this router reads the system's
    state to determine the right depth of intervention.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        custom_profiles: Optional[Dict[str, EffortProfile]] = None,
    ):
        self._profiles = dict(PROFILES)
        if custom_profiles:
            self._profiles = merge_profiles(self._profiles, custom_profiles)
        if config_path and config_path.exists():
            yaml_profiles = load_profiles_from_yaml(config_path)
            self._profiles = merge_profiles(self._profiles, yaml_profiles)
        self._last_deep: Optional[float] = None  # timestamp of last deep run
        self._error_history: List[str] = []

    @property
    def profiles(self) -> Dict[str, EffortProfile]:
        return dict(self._profiles)

    def determine_effort(
        self,
        override: Optional[EffortLevel] = None,
        time_since_last_deep_hours: Optional[float] = None,
        known_errors: Optional[List[str]] = None,
        disk_pressure: Optional[float] = None,  # 0.0-1.0
    ) -> EffortLevel:
        """Determine the appropriate effort level for this run.
        
        Args:
            override: Manual override (from cron job arg or CLI flag).
            time_since_last_deep: Hours since last deep run.
            known_errors: List of active error descriptions.
            disk_pressure: Disk usage as fraction (0.3 = 30% used).
        
        Returns:
            The resolved EffortLevel.
        """
        # 1. Manual override always wins
        if override is not None:
            logger.info("Eir effort: manual override → %s", override.value)
            return override

        errors = known_errors or []
        pressure = disk_pressure or 0.0

        # 2. Emergency: more than 3 active errors
        if len(errors) > 3:
            logger.info("Eir effort: %d errors → emergency", len(errors))
            return EffortLevel.EMERGENCY

        # 3. Deep: overdue (>24h since last deep check)
        if time_since_last_deep_hours is not None and time_since_last_deep_hours > 24:
            logger.info("Eir effort: last deep %.1fh ago → deep", time_since_last_deep_hours)
            return EffortLevel.DEEP

        # 4. Standard: some errors or moderate disk pressure
        if len(errors) > 0 or pressure > 0.7:
            logger.info("Eir effort: %d errors, %.0f%% disk → standard", len(errors), pressure * 100)
            return EffortLevel.STANDARD

        # 5. Default: quick pulse check
        logger.info("Eir effort: healthy system → quick")
        return EffortLevel.QUICK

    def resolve_checks(self, effort: EffortLevel) -> Dict[str, List[str]]:
        """Get the active checks for a given effort level."""
        profile_name = effort.value
        profile = self._profiles.get(profile_name, STANDARD_PROFILE)
        return profile.all_active_checks()

    def estimate_duration(self, effort: EffortLevel) -> float:
        """Estimate how long a run will take in seconds."""
        profile = self._profiles.get(effort.value, STANDARD_PROFILE)
        return profile.total_cost()

    def record_run(self, effort: EffortLevel, errors: List[str]) -> None:
        """Record the result of a run for future routing decisions."""
        if effort == EffortLevel.DEEP:
            self._last_deep = time.time()
        self._error_history = errors[-10:]  # Keep last 10


class ModelRouter:
    """Routes tasks to appropriate AI models based on complexity.
    
    Like a skáld choosing the right verse form for the subject,
    the ModelRouter matches task complexity to model capability.
    
    Diagnostic tasks → lightweight models (fast, cheap)
    Semantic tasks → midweight models (embedding-aware)
    Reasoning tasks → midweight models (needs judgment)
    Complex tasks → heavyweight models (full reasoning)
    """

    def __init__(
        self,
        model_overrides: Optional[Dict[str, str]] = None,
        available_models: Optional[Set[str]] = None,
    ):
        self._overrides = model_overrides or {}
        self._available = available_models or set()

    def select_model(
        self,
        check_name: str,
        fallback: str = "glm-5.1",
    ) -> Dict[str, Any]:
        """Select the best model for a given check.
        
        Args:
            check_name: The diagnostic/maintenance check to run.
            fallback: Default model if nothing else is available.
        
        Returns:
            Dict with 'model', 'tier', 'max_tokens', 'complexity'.
        """
        # 1. Check for manual override
        if check_name in self._overrides:
            return {
                "model": self._overrides[check_name],
                "tier": "override",
                "max_tokens": 2000,
                "complexity": "manual",
            }

        # 2. Look up check in registry
        check_info = CHECK_REGISTRY.get(check_name)
        if check_info is None:
            # Unknown check — use fallback
            return {
                "model": fallback,
                "tier": "unknown",
                "max_tokens": 1000,
                "complexity": "unknown",
            }

        complexity = check_info["complexity"]
        tier_name = COMPLEXITY_TO_TIER[complexity]
        tier = MODEL_TIERS[tier_name]

        # 3. Find first available model in tier
        selected = fallback
        for model in tier["models"]:
            if not self._available or model in self._available:
                selected = model
                break

        return {
            "model": selected,
            "tier": tier_name,
            "max_tokens": tier["max_tokens"],
            "complexity": complexity.value,
        }

    def plan_run(
        self,
        checks: Dict[str, List[str]],
    ) -> Dict[str, Dict[str, Any]]:
        """Plan an entire run, assigning models to each check.
        
        Args:
            checks: Dict of layer_name → list_of_checks, as returned
                    by EffortRouter.resolve_checks().
        
        Returns:
            Dict of layer_name → {check_name: model_assignment}.
        """
        plan = {}
        for layer_name, layer_checks in checks.items():
            plan[layer_name] = {}
            for check in layer_checks:
                plan[layer_name][check] = self.select_model(check)
        return plan

    @staticmethod
    def should_use_ai(check_name: str) -> bool:
        """Determine if a check needs AI involvement at all.
        
        Most Eir checks are pure logic (SQL, filesystem, REST).
        Only a few need AI assistance:
        - promotion: needs judgment on what's worth promoting
        - dedup (semantic): needs embeddings
        - consolidation: needs pattern recognition
        """
        ai_checks = {"promotion", "consolidation"}
        return check_name in ai_checks