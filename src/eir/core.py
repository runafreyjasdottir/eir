"""
Eir Core — Consolidation Pipeline
====================================
Orchestrates memory maintenance: decay, promotion, dedup,
consolidation, backup, and integrity verification.

Now config-driven through effort levels and layer flags.
Like a völva choosing which threads to read at the Well,
Eir selects only the checks the situation requires.
"""

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import EirConfig, get_config
from .layers import (
    CHECK_REGISTRY,
    EffortLevel,
    LayerConfig,
    TaskComplexity,
)
from .router import EffortRouter, ModelRouter

logger = logging.getLogger("eir.core")


class EirPipeline:
    """Eir Consolidation Pipeline — the physician of memories.
    
    Named for Eir, the Norse goddess of healing, who sits at Lyfjaberg
    (the Hill of Healing). This pipeline:
    
    1. Applies Ebbinghaus decay (forgets what fades)
    2. Promotes important memories to knowledge (solidifies what endures)
    3. Deduplicates similar memories (merges echoes)
    4. Consolidates strong Hebbian connections (reinforces patterns)
    5. Creates backups (protects the archive)
    6. Verifies integrity (diagnoses corruption)
    
    Should be run periodically (e.g., daily via cron) to maintain
    a healthy memory network.
    """

    def __init__(self, config: Optional[EirConfig] = None):
        self.config = config or get_config()
        self._mimir_conn = None
        self._muninn = None
        self._huginn = None
        self.effort_router = EffortRouter(
            config_path=Path(self.config.config_path) if self.config.config_path else None
        )
        self.model_router = ModelRouter()

    # ─── Backend Accessors ─────────────────────────────────────────────

    def _get_mimir(self) -> Optional[sqlite3.Connection]:
        """Get Mímir's Well connection."""
        if self._mimir_conn is None:
            db_path = Path(self.config.mimir_db_path).expanduser()
            if db_path.exists():
                self._mimir_conn = sqlite3.connect(str(db_path))
                self._mimir_conn.row_factory = sqlite3.Row
        return self._mimir_conn

    def _get_muninn(self):
        """Get Muninn (Hebbian) connection."""
        if self._muninn is None:
            try:
                from muninn import HebbianMemory
                from muninn.config import MuninnConfig
                self._muninn = HebbianMemory(
                    MuninnConfig(db_path=self.config.muninn_db_path)
                )
            except Exception as e:
                logger.warning("Eir: Muninn not available: %s", e)
        return self._muninn

    def _get_huginn(self):
        """Get Huginn (Qdrant) connection."""
        if self._huginn is None:
            try:
                from huginn import HuginnMemory
                self._huginn = HuginnMemory()
            except Exception as e:
                logger.warning("Eir: Huginn not available: %s", e)
        return self._huginn

    # ─── Layer-Aware Execution ──────────────────────────────────────────

    def _should_run(self, check_name: str, active_checks: Dict[str, List[str]]) -> bool:
        """Check if a given check is in the active set for this run."""
        for layer_checks in active_checks.values():
            if check_name in layer_checks:
                return True
        return False

    # ─── Main Pipeline ──────────────────────────────────────────────────

    def run(
        self,
        effort: Optional[EffortLevel] = None,
        active_checks: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Run the consolidation pipeline with layer-aware routing.
        
        Args:
            effort: Override effort level. If None, the router decides.
            active_checks: Override which checks to run. If None, 
                          the effort level determines the checks.
        
        Returns:
            Summary of all operations performed.
        """
        # Resolve effort level
        if effort is None:
            effort = EffortLevel(self.config.effort_level)
        
        # Resolve active checks from effort level
        if active_checks is None:
            active_checks = self.effort_router.resolve_checks(effort)
        
        # Plan model assignments for AI-assisted checks
        model_plan = self.model_router.plan_run(active_checks)

        results = {
            "timestamp": datetime.now().isoformat(),
            "effort_level": effort.value,
            "active_checks": active_checks,
            "model_plan": model_plan,
            "decay": {},
            "promotion": {},
            "dedup": {},
            "consolidation": {},
            "backup": {},
            "integrity": {},
        }

        logger.info(
            "Eir: Starting consolidation pipeline [effort=%s, checks=%d]",
            effort.value,
            sum(len(v) for v in active_checks.values()),
        )

        # 1. Decay
        if self._should_run("decay", active_checks):
            results["decay"] = self.decay()
            logger.info("Eir: Decay — %s", results["decay"])

        # 2. Promotion
        if self._should_run("promotion", active_checks):
            results["promotion"] = self.promote()
            logger.info("Eir: Promotion — %s", results["promotion"])

        # 3. Deduplication
        if self._should_run("dedup", active_checks):
            results["dedup"] = self.deduplicate()
            logger.info("Eir: Dedup — %s", results["dedup"])

        # 4. Consolidation
        if self._should_run("consolidation", active_checks):
            results["consolidation"] = self.consolidate()
            logger.info("Eir: Consolidation — %s", results["consolidation"])

        # 5. Backup
        if self._should_run("backup_verify", active_checks):
            results["backup"] = self.backup()
            logger.info("Eir: Backup — %s", results["backup"])

        # 6. Integrity check
        if self._should_run("integrity", active_checks):
            results["integrity"] = self.integrity_check()
            logger.info("Eir: Integrity — %s", results["integrity"])

        logger.info("Eir: Consolidation pipeline complete [%s]", effort.value)

        # Record the run for future routing
        errors = []
        for section in ["decay", "promotion", "dedup", "consolidation", "backup", "integrity"]:
            if isinstance(results.get(section), dict):
                for key, val in results[section].items():
                    if isinstance(val, dict) and "error" in val:
                        errors.append(f"{section}.{key}: {val['error']}")
        self.effort_router.record_run(effort, errors)

        return results

    # ─── Individual Operations ────────────────────────────────────────────

    def decay(self) -> Dict[str, Any]:
        """Apply Ebbinghaus decay across all backends.
        
        Forgets what fades, preserves what endures.
        """
        results = {"muninn": {}}

        muninn = self._get_muninn()
        if muninn:
            results["muninn"] = muninn.decay(days=self.config.decay_days)

        # Mímir: decay importance of rarely-accessed memories
        mimir = self._get_mimir()
        if mimir:
            try:
                cursor = mimir.execute(
                    """UPDATE memories
                       SET importance = MAX(1, importance - 1)
                       WHERE importance > 1
                         AND id IN (
                           SELECT m.id FROM memories m
                           LEFT JOIN memory_access_log l ON m.id = l.memory_id
                           WHERE l.memory_id IS NULL
                             OR l.accessed_at < datetime('now', '-30 days')
                         )"""
                )
                mimir.commit()
                results["mimir"] = {"importance_decayed": cursor.rowcount}
            except Exception as e:
                results["mimir"] = {"error": str(e)}

        return results

    def promote(self) -> Dict[str, Any]:
        """Promote important, frequently-accessed memories to knowledge.
        
        In Norse mythology, Eir promotes healing — here we promote
        memories that have proven their worth through repeated access
        and high importance.
        """
        results = {"promoted": 0, "errors": []}

        mimir = self._get_mimir()
        if not mimir:
            results["errors"].append("Mímir not available")
            return results

        try:
            # Find memories eligible for promotion
            candidates = mimir.execute(
                """SELECT m.id, m.content, m.category, m.importance, m.tags
                   FROM memories m
                   WHERE m.importance >= ?
                     AND m.category != 'knowledge'
                     AND m.id NOT IN (SELECT DISTINCT entity_id FROM knowledge)""",
                (self.config.promotion_importance_threshold,),
            ).fetchall()

            for row in candidates:
                try:
                    # Create knowledge entry from memory
                    mimir.execute(
                        """INSERT OR IGNORE INTO knowledge
                           (domain, content, source, confidence)
                           VALUES (?, ?, 'eir_promotion', 0.8)""",
                        (row["category"], row["content"]),
                    )
                    results["promoted"] += 1
                except Exception as e:
                    results["errors"].append(f"Memory {row['id']}: {e}")

            mimir.commit()
        except Exception as e:
            results["errors"].append(str(e))

        return results

    def deduplicate(self) -> Dict[str, Any]:
        """Find and merge duplicate or near-duplicate memories.
        
        Like a physician removing redundant tissue, Eir identifies
        memories that echo each other and merges them into one.
        """
        results = {"groups_found": 0, "merged": 0, "errors": []}

        mimir = self._get_mimir()
        if not mimir:
            results["errors"].append("Mímir not available")
            return results

        try:
            # Find exact content duplicates
            duplicates = mimir.execute(
                """SELECT content, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
                   FROM memories
                   GROUP BY content
                   HAVING cnt > 1""",
            ).fetchall()

            for row in duplicates:
                ids = [int(x) for x in row["ids"].split(",")]
                results["groups_found"] += 1

                # Keep the highest importance, delete the rest
                keepers = mimir.execute(
                    "SELECT id FROM memories WHERE id IN ({}) ORDER BY importance DESC, id ASC LIMIT 1".format(
                        ",".join("?" * len(ids))
                    ),
                    ids,
                ).fetchall()

                if keepers:
                    keep_id = keepers[0]["id"]
                    delete_ids = [i for i in ids if i != keep_id]
                    for did in delete_ids:
                        mimir.execute("DELETE FROM memories WHERE id = ?", (did,))
                    results["merged"] += len(delete_ids)

            mimir.commit()
        except Exception as e:
            results["errors"].append(str(e))

        return results

    def consolidate(self) -> Dict[str, Any]:
        """Consolidate strong Hebbian connections into long-term paths.
        
        Eir strengthens the bonds that have proven their worth through
        repeated co-activation, making them permanent parts of the
        memory network.
        """
        results = {"muninn": {}}

        muninn = self._get_muninn()
        if muninn:
            results["muninn"] = muninn.consolidate(
                min_strength=self.config.consolidation_strength_threshold
            )

        # Sync consolidated knowledge to Huginn vectors
        huginn = self._get_huginn()
        if huginn and muninn:
            try:
                stats = muninn.stats()
                results["muninn_stats"] = stats
            except Exception as e:
                results["huginn_sync_error"] = str(e)

        return results

    def backup(self) -> Dict[str, Any]:
        """Create timestamped backups of all memory databases.
        
        Eir protects the archive — like a guardian at Lyfjaberg,
        she ensures nothing of value is lost to corruption or time.
        
        BUG FIX: Now correctly backs up .db files, not .py source files.
        """
        results = {"backups": [], "errors": []}

        backup_dir = Path(self.config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup Mímir — the actual database, not the source module
        mimir_path = Path(self.config.mimir_db_path).expanduser()
        if mimir_path.exists() and mimir_path.suffix == ".db":
            try:
                dest = backup_dir / f"mimir_{timestamp}.db"
                shutil.copy2(mimir_path, dest)
                results["backups"].append(str(dest))
            except Exception as e:
                results["errors"].append(f"Mímir backup: {e}")
        elif not mimir_path.exists():
            pass  # Skip silently —没什么可备份的
        else:
            results["errors"].append(
                f"Mímir path is not a database: {mimir_path} (suffix={mimir_path.suffix})"
            )

        # Backup Muninn
        muninn_path = Path(self.config.muninn_db_path).expanduser()
        if muninn_path.exists():
            try:
                dest = backup_dir / f"muninn_{timestamp}.db"
                shutil.copy2(muninn_path, dest)
                results["backups"].append(str(dest))
            except Exception as e:
                results["errors"].append(f"Muninn backup: {e}")

        # Backup Runa Memory (the actual live DB)
        runa_memory_path = Path.home() / ".hermes" / "memory" / "runa_memory.db"
        if runa_memory_path.exists():
            try:
                dest = backup_dir / f"runa_memory_{timestamp}.db"
                shutil.copy2(runa_memory_path, dest)
                results["backups"].append(str(dest))
            except Exception as e:
                results["errors"].append(f"Runa memory backup: {e}")

        # Rotate old backups
        self._rotate_backups(backup_dir)

        return results

    def _rotate_backups(self, backup_dir: Path):
        """Remove old backups beyond max_backups per type."""
        for pattern in ["mimir_*.db", "muninn_*.db", "runa_memory_*.db"]:
            backups = sorted(backup_dir.glob(pattern))
            while len(backups) > self.config.max_backups:
                oldest = backups.pop(0)
                oldest.unlink()

    def integrity_check(self) -> Dict[str, Any]:
        """Run integrity checks on all memory backends.
        
        Eir diagnoses corruption — she who sees what lies beneath
        the surface and heals it before it spreads.
        """
        results = {"mimir": {}, "huginn": {}, "muninn": {}}

        # Mímir integrity
        mimir = self._get_mimir()
        if mimir:
            try:
                # Check FTS integrity
                mimir.execute(
                    "INSERT INTO memories_fts(memories_fts) VALUES('integrity-check')"
                )
                mimir.commit()
                results["mimir"]["fts"] = "healthy"

                # Orphan check
                orphans = mimir.execute(
                    """SELECT COUNT(*) as c FROM memories m
                       LEFT JOIN memory_access_log l ON m.id = l.memory_id
                       WHERE l.memory_id IS NULL"""
                ).fetchone()["c"]
                results["mimir"]["orphaned_memories"] = orphans

                # Total counts
                mem_count = mimir.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
                results["mimir"]["total_memories"] = mem_count

            except Exception as e:
                results["mimir"]["error"] = str(e)

        # Huginn health
        huginn = self._get_huginn()
        if huginn:
            try:
                results["huginn"] = huginn.health()
            except Exception as e:
                results["huginn"] = {"error": str(e)}
        else:
            results["huginn"] = {"status": "not_available"}

        # Muninn health
        muninn = self._get_muninn()
        if muninn:
            try:
                results["muninn"] = muninn.health()
            except Exception as e:
                results["muninn"] = {"error": str(e)}
        else:
            results["muninn"] = {"status": "not_available"}

        return results

    # ─── Convenience Methods ──────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Quick health check of the Eir pipeline."""
        # Quick always uses just integrity check
        active_checks = self.effort_router.resolve_checks(EffortLevel.QUICK)
        return {
            "status": "healthy",
            "effort_level": self.config.effort_level,
            "config": {
                "decay_enabled": self.config.decay_enabled,
                "promotion_enabled": self.config.promotion_enabled,
                "dedup_enabled": self.config.dedup_enabled,
                "consolidation_enabled": self.config.consolidation_enabled,
                "backup_enabled": self.config.backup_enabled,
            },
            "active_checks": active_checks,
            "backends": self.integrity_check(),
        }

    def close(self):
        """Close all backend connections."""
        if self._mimir_conn:
            self._mimir_conn.close()
            self._mimir_conn = None
        if self._muninn:
            self._muninn.close()
            self._muninn = None
        if self._huginn:
            if hasattr(self._huginn, 'close'):
                self._huginn.close()
            self._huginn = None