"""
Eir Core — Consolidation Pipeline
====================================
Orchestrates memory maintenance: decay, promotion, dedup,
consolidation, backup, and integrity verification.
"""

import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import EirConfig, get_config

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

    # ─── Main Pipeline ────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Run the full consolidation pipeline.
        
        Returns a summary of all operations performed.
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "decay": {},
            "promotion": {},
            "dedup": {},
            "consolidation": {},
            "backup": {},
            "integrity": {},
        }

        logger.info("Eir: Starting consolidation pipeline")

        # 1. Decay
        if self.config.decay_enabled:
            results["decay"] = self.decay()
            logger.info("Eir: Decay — %s", results["decay"])

        # 2. Promotion
        if self.config.promotion_enabled:
            results["promotion"] = self.promote()
            logger.info("Eir: Promotion — %s", results["promotion"])

        # 3. Deduplication
        if self.config.dedup_enabled:
            results["dedup"] = self.deduplicate()
            logger.info("Eir: Dedup — %s", results["dedup"])

        # 4. Consolidation
        if self.config.consolidation_enabled:
            results["consolidation"] = self.consolidate()
            logger.info("Eir: Consolidation — %s", results["consolidation"])

        # 5. Backup
        if self.config.backup_enabled:
            results["backup"] = self.backup()
            logger.info("Eir: Backup — %s", results["backup"])

        # 6. Integrity check
        if self.config.integrity_check_enabled:
            results["integrity"] = self.integrity_check()
            logger.info("Eir: Integrity — %s", results["integrity"])

        logger.info("Eir: Consolidation pipeline complete")
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
        """
        results = {"backups": [], "errors": []}

        backup_dir = Path(self.config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup Mímir
        mimir_path = Path(self.config.mimir_db_path).expanduser()
        if mimir_path.exists():
            try:
                dest = backup_dir / f"mimir_{timestamp}.py"
                shutil.copy2(mimir_path, dest)
                results["backups"].append(str(dest))
            except Exception as e:
                results["errors"].append(f"Mímir backup: {e}")

        # Backup Muninn
        muninn_path = Path(self.config.muninn_db_path).expanduser()
        if muninn_path.exists():
            try:
                dest = backup_dir / f"muninn_{timestamp}.db"
                shutil.copy2(muninn_path, dest)
                results["backups"].append(str(dest))
            except Exception as e:
                results["errors"].append(f"Muninn backup: {e}")

        # Rotate old backups
        self._rotate_backups(backup_dir)

        return results

    def _rotate_backups(self, backup_dir: Path):
        """Remove old backups beyond max_backups per type."""
        for pattern in ["mimir_*.py", "muninn_*.db"]:
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
                fts_check = mimir.execute(
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
        return {
            "status": "healthy",
            "config": {
                "decay_enabled": self.config.decay_enabled,
                "promotion_enabled": self.config.promotion_enabled,
                "dedup_enabled": self.config.dedup_enabled,
                "consolidation_enabled": self.config.consolidation_enabled,
                "backup_enabled": self.config.backup_enabled,
            },
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