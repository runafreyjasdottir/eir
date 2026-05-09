"""
Eir Configuration
==================
Named for the Norse goddess of healing and medicine.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import os


@dataclass
class EirConfig:
    """Configuration for the Eir Consolidation Pipeline.
    
    Eir is the best of physicians in Norse mythology. She sits at Lyfjaberg
    (the Hill of Healing), bringing restoration and consolidation to what
    has been worn down by time.
    """
    # ─── Memory Backends ────────────────────────────────────────────────
    mimir_db_path: str = os.path.expanduser("~/.hermes/memory/runa_memory.py")
    huginn_url: str = "http://localhost:6333"
    muninn_db_path: str = os.path.expanduser("~/.hermes/memory/muninn_hebbian.db")
    
    # ─── Decay Settings ────────────────────────────────────────────────
    decay_enabled: bool = True
    decay_days: float = 1.0                 # Simulate 1 day of decay per cycle
    
    # ─── Promotion Settings ─────────────────────────────────────────────
    promotion_enabled: bool = True
    promotion_importance_threshold: int = 7  # Importance ≥ 7 eligible for promotion
    promotion_access_threshold: int = 3      # Accessed ≥ 3 times eligible for promotion
    
    # ─── Deduplication Settings ─────────────────────────────────────────
    dedup_enabled: bool = True
    dedup_similarity_threshold: float = 0.85  # Cosine similarity for dedup
    
    # ─── Consolidation Settings ─────────────────────────────────────────
    consolidation_enabled: bool = True
    consolidation_strength_threshold: float = 0.6  # Muninn strength for consolidation
    
    # ─── Backup Settings ────────────────────────────────────────────────
    backup_enabled: bool = True
    backup_dir: str = os.path.expanduser("~/.hermes/memory/backups")
    max_backups: int = 7
    
    # ─── Integrity Settings ──────────────────────────────────────────────
    integrity_check_enabled: bool = True


# ─── Singleton Config ──────────────────────────────────────────────────────
_config: Optional[EirConfig] = None


def get_config() -> EirConfig:
    """Get or create the global Eir configuration."""
    global _config
    if _config is None:
        _config = EirConfig()
    return _config


def set_config(config: EirConfig):
    """Override the global configuration."""
    global _config
    _config = config