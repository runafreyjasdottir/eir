"""
Eir Layers — Feature Flag Architecture
========================================
Diagnostic and maintenance layers that can be toggled on/off
via YAML config, routed by effort level and conditions.

Named for the nine layers of Yggdrasil's roots — each world
has its own depth, and the healer must choose how deep to go.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class EffortLevel(Enum):
    """How deep Eir should dig — quick surface check or full surgery."""
    QUICK = "quick"        # ≤30s — integrity only, no mutation
    STANDARD = "standard"  # ≤2min — core maintenance + integrity
    DEEP = "deep"          # ≤10min — full pipeline + semantic operations
    EMERGENCY = "emergency"  # no limit — everything, used when something's broken


class TaskComplexity(Enum):
    """What kind of cognitive load this task requires."""
    DIAGNOSTIC = "diagnostic"      # Pattern matching, counting, SQL — no AI needed
    SEMANTIC = "semantic"          # Needs embedding comparison — lightweight model
    REASONING = "reasoning"       # Needs judgment — mid-tier model
    COMPLEX = "complex"           # Multi-step reasoning — best model available


# ─── Check Definitions ────────────────────────────────────────────────────
# Each check belongs to a layer and has a cost + complexity

CHECK_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Mímir checks
    "integrity":       {"layer": "mimir",  "cost": 0.1, "complexity": TaskComplexity.DIAGNOSTIC},
    "decay":           {"layer": "mimir",  "cost": 0.3, "complexity": TaskComplexity.DIAGNOSTIC},
    "promotion":       {"layer": "mimir",  "cost": 0.5, "complexity": TaskComplexity.REASONING},
    "dedup":           {"layer": "mimir",  "cost": 0.4, "complexity": TaskComplexity.SEMANTIC},
    "compress":        {"layer": "mimir",  "cost": 0.6, "complexity": TaskComplexity.REASONING},
    "fts_rebuild":     {"layer": "mimir",  "cost": 0.2, "complexity": TaskComplexity.DIAGNOSTIC},
    "orphan_cleanup":  {"layer": "mimir",  "cost": 0.2, "complexity": TaskComplexity.DIAGNOSTIC},

    # Huginn checks
    "collections":     {"layer": "huginn", "cost": 0.1, "complexity": TaskComplexity.DIAGNOSTIC},
    "embedder":        {"layer": "huginn", "cost": 0.2, "complexity": TaskComplexity.DIAGNOSTIC},
    "vectors":         {"layer": "huginn", "cost": 0.3, "complexity": TaskComplexity.SEMANTIC},
    "reindex":         {"layer": "huginn", "cost": 0.8, "complexity": TaskComplexity.SEMANTIC},

    # Muninn checks
    "health":          {"layer": "muninn", "cost": 0.1, "complexity": TaskComplexity.DIAGNOSTIC},
    "consolidation":   {"layer": "muninn", "cost": 0.5, "complexity": TaskComplexity.REASONING},
    "hebbian_decay":   {"layer": "muninn", "cost": 0.3, "complexity": TaskComplexity.DIAGNOSTIC},

    # Kista checks
    "vault_integrity":  {"layer": "kista", "cost": 0.1, "complexity": TaskComplexity.DIAGNOSTIC},
    "key_rotation":     {"layer": "kista", "cost": 0.2, "complexity": TaskComplexity.DIAGNOSTIC},
    "backup_verify":    {"layer": "kista", "cost": 0.3, "complexity": TaskComplexity.DIAGNOSTIC},

    # Nervus checks
    "socket":          {"layer": "nervus", "cost": 0.05, "complexity": TaskComplexity.DIAGNOSTIC},
    "feed":            {"layer": "nervus", "cost": 0.05, "complexity": TaskComplexity.DIAGNOSTIC},
    "impulse_count":   {"layer": "nervus", "cost": 0.05, "complexity": TaskComplexity.DIAGNOSTIC},
    "latency":         {"layer": "nervus", "cost": 0.1, "complexity": TaskComplexity.DIAGNOSTIC},
}


@dataclass
class LayerConfig:
    """A single diagnostic/maintenance layer with toggleable checks."""
    enabled: bool = True
    checks: List[str] = field(default_factory=list)

    def active_checks(self) -> List[str]:
        """Return only the checks that exist in the registry."""
        return [c for c in self.checks if c in CHECK_REGISTRY]

    def total_cost(self) -> float:
        """Sum of costs for active checks."""
        return sum(CHECK_REGISTRY[c]["cost"] for c in self.active_checks())


@dataclass 
class EffortProfile:
    """Complete configuration for a given effort level."""
    name: str
    description: str = ""
    max_duration: int = 120  # seconds
    layers: Dict[str, LayerConfig] = field(default_factory=dict)

    def active_checks_for_layer(self, layer_name: str) -> List[str]:
        """Get active checks for a specific layer."""
        layer = self.layers.get(layer_name)
        if not layer or not layer.enabled:
            return []
        return layer.active_checks()

    def all_active_checks(self) -> Dict[str, List[str]]:
        """Get all active checks organized by layer."""
        return {
            name: layer.active_checks()
            for name, layer in self.layers.items()
            if layer.enabled and layer.active_checks()
        }

    def total_cost(self) -> float:
        """Total cost estimate across all active layers."""
        return sum(layer.total_cost() for layer in self.layers.values() if layer.enabled)


# ─── Default Effort Profiles ──────────────────────────────────────────────

QUICK_PROFILE = EffortProfile(
    name="quick",
    description="Fast daily pulse — integrity checks only, no mutations",
    max_duration=30,
    layers={
        "mimir": LayerConfig(enabled=True, checks=["integrity"]),
        "huginn": LayerConfig(enabled=True, checks=["collections"]),
        "muninn": LayerConfig(enabled=False),
        "kista": LayerConfig(enabled=True, checks=["vault_integrity"]),
        "nervus": LayerConfig(enabled=False),
    },
)

STANDARD_PROFILE = EffortProfile(
    name="standard",
    description="Standard daily — core maintenance + integrity",
    max_duration=120,
    layers={
        "mimir": LayerConfig(enabled=True, checks=["integrity", "decay", "dedup", "compress"]),
        "huginn": LayerConfig(enabled=True, checks=["collections", "embedder"]),
        "muninn": LayerConfig(enabled=True, checks=["health"]),
        "kista": LayerConfig(enabled=True, checks=["vault_integrity", "backup_verify"]),
        "nervus": LayerConfig(enabled=True, checks=["socket", "feed"]),
    },
)

DEEP_PROFILE = EffortProfile(
    name="deep",
    description="Deep weekly — full pipeline including semantic operations",
    max_duration=600,
    layers={
        "mimir": LayerConfig(enabled=True, checks=[
            "integrity", "decay", "promotion", "dedup", "compress", "fts_rebuild", "orphan_cleanup"
        ]),
        "huginn": LayerConfig(enabled=True, checks=["collections", "embedder", "vectors", "reindex"]),
        "muninn": LayerConfig(enabled=True, checks=["health", "consolidation", "hebbian_decay"]),
        "kista": LayerConfig(enabled=True, checks=["vault_integrity", "key_rotation", "backup_verify"]),
        "nervus": LayerConfig(enabled=True, checks=["socket", "feed", "impulse_count", "latency"]),
    },
)

EMERGENCY_PROFILE = EffortProfile(
    name="emergency",
    description="Everything — used when diagnosing failures",
    max_duration=0,  # no limit
    layers={
        "mimir": LayerConfig(enabled=True, checks=[
            "integrity", "decay", "promotion", "dedup", "compress", "fts_rebuild", "orphan_cleanup"
        ]),
        "huginn": LayerConfig(enabled=True, checks=["collections", "embedder", "vectors", "reindex"]),
        "muninn": LayerConfig(enabled=True, checks=["health", "consolidation", "hebbian_decay"]),
        "kista": LayerConfig(enabled=True, checks=["vault_integrity", "key_rotation", "backup_verify"]),
        "nervus": LayerConfig(enabled=True, checks=["socket", "feed", "impulse_count", "latency"]),
    },
)


# ─── Profile Resolution ───────────────────────────────────────────────────

PROFILES: Dict[str, EffortProfile] = {
    "quick": QUICK_PROFILE,
    "standard": STANDARD_PROFILE,
    "deep": DEEP_PROFILE,
    "emergency": EMERGENCY_PROFILE,
}


def get_profile(effort: EffortLevel) -> EffortProfile:
    """Get the effort profile for a given level."""
    return PROFILES[effort.value]


def load_profiles_from_yaml(path: Path) -> Dict[str, EffortProfile]:
    """Load custom effort profiles from a YAML config file.
    
    YAML format:
    
        effort_levels:
          quick:
            description: "Fast pulse"
            max_duration: 30
            layers:
              mimir:
                enabled: true
                checks: [integrity]
              huginn:
                enabled: true
                checks: [collections]
    """
    if not path.exists():
        return {}

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    profiles = {}
    for name, cfg in raw.get("effort_levels", {}).items():
        layers = {}
        for layer_name, layer_cfg in cfg.get("layers", {}).items():
            layers[layer_name] = LayerConfig(
                enabled=layer_cfg.get("enabled", True),
                checks=layer_cfg.get("checks", []),
            )
        profiles[name] = EffortProfile(
            name=name,
            description=cfg.get("description", ""),
            max_duration=cfg.get("max_duration", 120),
            layers=layers,
        )
    return profiles


def merge_profiles(
    builtin: Dict[str, EffortProfile],
    custom: Dict[str, EffortProfile],
) -> Dict[str, EffortProfile]:
    """Merge custom profiles into builtins. Custom overrides by name."""
    merged = dict(builtin)
    merged.update(custom)
    return merged