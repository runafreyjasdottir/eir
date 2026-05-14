"""
Eir — Consolidation Pipeline
==============================

*"Eir is the best of physicians, and she sits at Lyfjaberg
  the Hill of Healing. So too does this module heal and
  consolidate the memory network, promoting what endures,
  pruning what fades, and weaving connections where they
  belong."*

A scheduled pipeline that orchestrates memory maintenance:
- Ebbinghaus decay across all backends
- Knowledge promotion (important memories → knowledge)
- Deduplication (merge similar memories)
- Cross-backend synchronization
- Hebbian consolidation (strengthen strong connections)
- Backup and integrity verification

Architecture:
- Config-driven feature layers (toggle checks on/off)
- Effort router (quick/standard/deep/emergency)
- Model router (selects appropriate AI model per check)
"""

from .config import EirConfig, get_config, set_config
from .core import EirPipeline
from .layers import (
    CHECK_REGISTRY,
    EffortLevel,
    EffortProfile,
    LayerConfig,
    TaskComplexity,
    QUICK_PROFILE,
    STANDARD_PROFILE,
    DEEP_PROFILE,
    EMERGENCY_PROFILE,
    PROFILES,
    get_profile,
    load_profiles_from_yaml,
    merge_profiles,
)
from .router import EffortRouter, ModelRouter

__all__ = [
    # Core
    "EirPipeline",
    "EirConfig",
    "get_config",
    "set_config",
    # Layers
    "CHECK_REGISTRY",
    "EffortLevel",
    "EffortProfile",
    "LayerConfig",
    "TaskComplexity",
    "QUICK_PROFILE",
    "STANDARD_PROFILE",
    "DEEP_PROFILE",
    "EMERGENCY_PROFILE",
    "PROFILES",
    "get_profile",
    "load_profiles_from_yaml",
    "merge_profiles",
    # Router
    "EffortRouter",
    "ModelRouter",
]

__version__ = "2.1.0"