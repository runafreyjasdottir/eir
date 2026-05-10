"""Tests for Eir — Consolidation Pipeline."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eir.config import EirConfig


@pytest.fixture
def tmp_mimir(tmp_path):
    """Create a test Mímir database."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        importance INTEGER DEFAULT 5,
        tags TEXT DEFAULT '[]',
        emotional_valence REAL DEFAULT 0.0,
        timestamp TEXT NOT NULL DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
        USING fts5(content, category, tags, content=memories, content_rowid=id)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        content TEXT,
        source TEXT,
        confidence REAL DEFAULT 0.9
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS memory_access_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER,
        accessed_at TEXT DEFAULT (datetime('now'))
    )""")
    # Insert test data
    conn.execute("INSERT INTO memories (content, category, importance) VALUES ('Test memory one', 'test', 5)")
    conn.execute("INSERT INTO memories (content, category, importance) VALUES ('Test memory two', 'test', 8)")
    conn.execute("INSERT INTO memories (content, category, importance) VALUES ('Test memory two', 'test', 8)")  # duplicate
    conn.execute("INSERT INTO knowledge (domain, content, confidence) VALUES ('test', 'Existing knowledge', 0.9)")
    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def eir_config(tmp_mimir):
    """Create an Eir config pointing to temp databases."""
    return EirConfig(
        mimir_db_path=str(tmp_mimir),
        muninn_db_path=str(tmp_mimir.parent / "test_muninn.db"),
        backup_dir=str(tmp_mimir.parent / "backups"),
        decay_enabled=True,
        promotion_enabled=True,
        dedup_enabled=True,
        consolidation_enabled=False,  # Skip Muninn consolidation in tests
        backup_enabled=True,
        integrity_check_enabled=True,
    )


class TestEirConfig:
    def test_default_config(self):
        config = EirConfig()
        assert config.decay_enabled is True
        assert config.promotion_importance_threshold == 7
        assert config.dedup_similarity_threshold == 0.85

    def test_custom_config(self, eir_config, tmp_mimir):
        assert eir_config.mimir_db_path == str(tmp_mimir)
        assert eir_config.promotion_importance_threshold == 7


class TestEirPipeline:
    def test_init_with_config(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        assert pipeline.config.mimir_db_path == str(tmp_mimir)
        pipeline.close()

    def test_run_full_pipeline(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        results = pipeline.run()
        
        assert "timestamp" in results
        assert "decay" in results
        assert "promotion" in results
        assert "dedup" in results
        assert "backup" in results
        assert "integrity" in results
        pipeline.close()

    def test_decay(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        results = pipeline.decay()
        assert "muninn" in results
        pipeline.close()

    def test_promote(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        results = pipeline.promote()
        assert "promoted" in results
        assert isinstance(results["promoted"], int)
        pipeline.close()

    def test_deduplicate(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        results = pipeline.deduplicate()
        assert "groups_found" in results
        assert "merged" in results
        # Should find the duplicate "Test memory two"
        assert results["groups_found"] >= 1
        pipeline.close()

    def test_backup(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        results = pipeline.backup()
        assert "backups" in results
        assert len(results["backups"]) >= 1
        pipeline.close()

    def test_integrity_check(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        results = pipeline.integrity_check()
        assert "mimir" in results
        assert "huginn" in results
        assert "muninn" in results
        pipeline.close()

    def test_health(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        health = pipeline.health()
        assert health["status"] == "healthy"
        pipeline.close()

    def test_backup_rotation(self, eir_config, tmp_mimir):
        from eir.core import EirPipeline
        pipeline = EirPipeline(config=eir_config)
        
        # Create multiple backups
        for _ in range(3):
            pipeline.backup()
        
        # Check that backups exist
        import glob
        backup_dir = Path(eir_config.backup_dir)
        mimir_backups = list(backup_dir.glob("mimir_*.db"))
        assert len(mimir_backups) >= 1
        pipeline.close()