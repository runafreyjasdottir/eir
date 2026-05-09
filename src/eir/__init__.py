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
"""

from .config import EirConfig, get_config, set_config
from .core import EirPipeline

__all__ = [
    "EirPipeline",
    "EirConfig",
    "get_config",
    "set_config",
]

__version__ = "1.0.0"