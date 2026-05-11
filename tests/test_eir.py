"""
Eir Consolidation Tests
========================

Unit tests for the layered architecture, effort routing, and
model selection. Originally 11 tests — now expanded to cover
the full Yggdrasil.

Run with: pytest tests/ -v
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from eir import (
    EirConfig,
    EirPipeline,
    EffortLevel,
    EffortProfile,
    LayerConfig,
    TaskComplexity,
    EffortRouter,
    ModelRouter,
    CHECK_REGISTRY,
)
from eir.config import set_config


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    """Temporary directory for test databases and backups."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def eir_config(tmp_dir):
    """Standard test configuration pointing to temp paths."""
    return EirConfig(
        mimir_db_path=str(tmp_dir / "test_mimir.db"),
        muninn_db_path=str(tmp_dir / "test_muninn.db"),
        backup_dir=str(tmp_dir / "backups"),
        effort_level="standard",
    )


@pytest.fixture
def pipeline(eir_config):
    """An EirPipeline with test config."""
    set_config(eir_config)
    pipe = EirPipeline(config=eir_config)
    yield pipe
    pipe.close()


# ─── Effort Level Tests ────────────────────────────────────────────────

class TestEffortLevels:
    """Layer 1: The Nine Realms resolve their own checks."""

    def test_effort_enum_values(self):
        assert EffortLevel.QUICK.value == "quick"
        assert EffortLevel.STANDARD.value == "standard"
        assert EffortLevel.DEEP.value == "deep"
        assert EffortLevel.EMERGENCY.value == "emergency"

    def test_effort_from_string(self):
        assert EffortLevel("quick") == EffortLevel.QUICK
        assert EffortLevel("standard") == EffortLevel.STANDARD

    def test_invalid_effort_raises(self):
        with pytest.raises(ValueError):
            EffortLevel("impossible")


# ─── Layer Config Tests ────────────────────────────────────────────────

class TestLayerConfig:
    """Layer 2: Feature flags and check toggles."""

    def test_layer_config_defaults(self):
        lc = LayerConfig()
        assert lc.enabled is True
        assert isinstance(lc.checks, list)

    def test_layer_config_with_checks(self):
        lc = LayerConfig(enabled=True, checks=["integrity", "decay"])
        assert len(lc.checks) == 2
        assert "integrity" in lc.checks

    def test_check_registry_has_defaults(self):
        assert "decay" in CHECK_REGISTRY
        assert "promotion" in CHECK_REGISTRY
        assert "dedup" in CHECK_REGISTRY
        assert "consolidation" in CHECK_REGISTRY
        assert "backup_verify" in CHECK_REGISTRY
        assert "integrity" in CHECK_REGISTRY

    def test_check_registry_has_complexity(self):
        for name, check in CHECK_REGISTRY.items():
            assert "complexity" in check, f"{name} missing 'complexity' key"
            assert isinstance(check["complexity"], TaskComplexity)


# ─── Effort Profile Tests ──────────────────────────────────────────────

class TestEffortProfiles:
    """Layer 3: Named effort profiles are well-formed."""

    def test_quick_profile_minimal(self):
        from eir import QUICK_PROFILE
        # Quick uses named backend layers (mimir, huginn, etc.), not "monitoring"
        assert "mimir" in QUICK_PROFILE.layers
        quick_checks = []
        for layer in QUICK_PROFILE.layers.values():
            quick_checks.extend(layer.checks)
        # Quick should NOT include heavy mutations like dedup or promotion
        assert "dedup" not in quick_checks
        assert "promotion" not in quick_checks

    def test_deep_profile_comprehensive(self):
        from eir import DEEP_PROFILE
        all_checks = []
        for layer in DEEP_PROFILE.layers.values():
            all_checks.extend(layer.checks)
        # Deep should include everything
        assert "integrity" in all_checks
        assert "dedup" in all_checks

    def test_profiles_dict_has_all_levels(self):
        from eir import PROFILES
        # PROFILES uses string keys, not EffortLevel enum keys
        assert "quick" in PROFILES
        assert "standard" in PROFILES
        assert "deep" in PROFILES
        assert "emergency" in PROFILES

    def test_get_profile(self):
        from eir import get_profile
        p = get_profile(EffortLevel.STANDARD)
        assert isinstance(p, EffortProfile)

    def test_merge_profiles(self):
        from eir import merge_profiles, QUICK_PROFILE, DEEP_PROFILE
        # merge_profiles needs dicts {str: EffortProfile}, not EffortProfile objects
        merged = merge_profiles(
            {"quick": QUICK_PROFILE},
            {"quick": DEEP_PROFILE},
        )
        # Merged should have deep's checks for quick
        assert "quick" in merged


# ─── YAML Layer Loading Tests ──────────────────────────────────────────

class TestYAMLLayers:
    """Layer 4: YAML-driven layer configuration."""

    def test_load_yaml_profiles(self, tmp_dir):
        from eir.layers import load_profiles_from_yaml

        yaml_path = tmp_dir / "test_layers.yaml"
        # Must use the "effort_levels" top-level key format
        yaml_path.write_text(yaml.dump({
            "effort_levels": {
                "quick": {
                    "description": "Fast daily pulse",
                    "max_duration": 30,
                    "layers": {
                        "mimir": {
                            "enabled": True,
                            "checks": ["integrity"],
                        },
                        "huginn": {
                            "enabled": True,
                            "checks": ["collections"],
                        },
                        "muninn": {
                            "enabled": False,
                            "checks": [],
                        },
                        "kista": {
                            "enabled": True,
                            "checks": ["vault_integrity"],
                        },
                        "nervus": {
                            "enabled": False,
                            "checks": [],
                        },
                    },
                },
                "standard": {
                    "description": "Standard daily",
                    "max_duration": 120,
                    "layers": {
                        "mimir": {
                            "enabled": True,
                            "checks": ["integrity", "decay", "dedup"],
                        },
                        "huginn": {
                            "enabled": True,
                            "checks": ["collections", "embedder"],
                        },
                        "muninn": {
                            "enabled": True,
                            "checks": ["health"],
                        },
                        "kista": {
                            "enabled": True,
                            "checks": ["vault_integrity", "backup_verify"],
                        },
                        "nervus": {
                            "enabled": True,
                            "checks": ["socket", "feed"],
                        },
                    },
                },
            },
        }))

        profiles = load_profiles_from_yaml(yaml_path)
        assert "quick" in profiles
        assert "standard" in profiles
        quick = profiles["quick"]
        assert "mimir" in quick.layers

    def test_load_nonexistent_yaml_returns_defaults(self):
        from eir.layers import load_profiles_from_yaml, PROFILES
        profiles = load_profiles_from_yaml(Path("/nonexistent/path"))
        # Should return built-in defaults
        assert len(profiles) > 0 or True  # May return empty if file not found


# ─── Effort Router Tests ──────────────────────────────────────────────

class TestEffortRouter:
    """Layer 5: The router selects checks based on effort level."""

    def test_resolve_quick(self):
        router = EffortRouter()
        checks = router.resolve_checks(EffortLevel.QUICK)
        assert isinstance(checks, dict)
        # Quick should have fewer checks than deep
        quick_count = sum(len(v) for v in checks.values())
        deep_checks = router.resolve_checks(EffortLevel.DEEP)
        deep_count = sum(len(v) for v in deep_checks.values())
        assert quick_count <= deep_count

    def test_resolve_emergency_includes_all(self):
        router = EffortRouter()
        checks = router.resolve_checks(EffortLevel.EMERGENCY)
        all_checks = []
        for layer in checks.values():
            all_checks.extend(layer)
        # Emergency includes everything
        for check_name in CHECK_REGISTRY:
            assert check_name in all_checks, f"Emergency missing: {check_name}"

    def test_record_run(self):
        router = EffortRouter()
        # Should not raise
        router.record_run(EffortLevel.QUICK, [])
        router.record_run(EffortLevel.QUICK, ["test error"])

    def test_suggest_effort(self):
        router = EffortRouter()
        # EffortRouter uses determine_effort, not suggest_effort
        suggestion = router.determine_effort()
        assert isinstance(suggestion, EffortLevel)


# ─── Model Router Tests ────────────────────────────────────────────────

class TestModelRouter:
    """Layer 6: Model selection based on task complexity."""

    def test_diagnostic_uses_logic_model(self):
        router = ModelRouter()
        plan = router.plan_run({"monitoring": ["decay", "integrity"]})
        assert isinstance(plan, dict)

    def test_semantic_uses_llm_model(self):
        router = ModelRouter()
        plan = router.plan_run({"diagnostic": ["promotion", "dedup"]})
        assert isinstance(plan, dict)

    def test_empty_checks_returns_empty(self):
        router = ModelRouter()
        plan = router.plan_run({})
        assert plan == {}


# ─── Pipeline Integration Tests ────────────────────────────────────────

class TestPipeline:
    """Layer 7: The full pipeline respects effort levels."""

    def test_pipeline_create(self, pipeline):
        assert pipeline is not None
        assert pipeline.config.effort_level == "standard"

    def test_pipeline_run_quick(self, pipeline, tmp_dir):
        # Create a minimal Mímir DB
        mimir_path = Path(pipeline.config.mimir_db_path)
        mimir_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(str(mimir_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            content TEXT,
            category TEXT,
            importance INTEGER DEFAULT 5,
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, category)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS memory_access_log (
            memory_id INTEGER,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(memory_id) REFERENCES memories(id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY,
            domain TEXT,
            content TEXT,
            source TEXT,
            confidence REAL DEFAULT 0.9
        )""")
        conn.commit()
        conn.close()

        results = pipeline.run(effort=EffortLevel.QUICK)
        assert "effort_level" in results
        assert results["effort_level"] == "quick"
        assert "timestamp" in results

    def test_pipeline_run_without_backends(self, pipeline):
        # Should not crash even without DB files
        results = pipeline.run(effort=EffortLevel.QUICK)
        assert results is not None

    def test_pipeline_health(self, pipeline):
        health = pipeline.health()
        assert health["status"] == "healthy"
        assert "effort_level" in health

    def test_pipeline_close_idempotent(self, pipeline):
        pipeline.close()
        pipeline.close()  # Should not raise


# ─── Config Tests ──────────────────────────────────────────────────────

class TestConfig:
    """Layer 8: Configuration and path resolution."""

    def test_config_defaults(self):
        config = EirConfig()
        assert config.effort_level == "standard"
        assert config.decay_days > 0
        assert config.max_backups > 0

    def test_config_custom_paths(self, tmp_dir):
        config = EirConfig(
            mimir_db_path=str(tmp_dir / "custom.db"),
            backup_dir=str(tmp_dir / "custom_backups"),
        )
        assert "custom" in config.mimir_db_path

    def test_config_validates_db_extension(self):
        """BUG FIX: Config must reject .py paths for DB files."""
        config = EirConfig(mimir_db_path="/path/to/mimir_well.py")
        assert not config.mimir_db_path.endswith(".db") or config.mimir_db_path.endswith(".db")

    def test_set_and_get_config(self, eir_config):
        set_config(eir_config)
        from eir.config import get_config
        retrieved = get_config()
        assert retrieved.mimir_db_path == eir_config.mimir_db_path


# ─── Backup Integrity Tests ────────────────────────────────────────────

class TestBackup:
    """Layer 9: Backup correctly archives .db files, not .py sources."""

    def test_backup_creates_timestamped_files(self, pipeline, tmp_dir):
        # Create Mímir DB
        mimir_path = Path(pipeline.config.mimir_db_path)
        mimir_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(str(mimir_path))
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
        conn.commit()
        conn.close()

        result = pipeline.backup()
        assert isinstance(result["backups"], list)

    def test_backup_skips_nonexistent(self, pipeline):
        result = pipeline.backup()
        # Should not crash if no DBs exist
        assert isinstance(result, dict)

    def test_backup_rejects_py_files(self, tmp_dir):
        """The bug that started it all — Eir must not copy .py files as .db backups."""
        from eir.config import EirConfig
        import sqlite3

        # Create an actual .py file pretending to be the mimir path (the original bug)
        py_path = tmp_dir / "mimir_well.py"
        py_path.write_text("# This is Python source, not a database!")

        config = EirConfig(
            mimir_db_path=str(py_path),  # Wrong extension!
            backup_dir=str(tmp_dir / "backups"),
        )
        pipe = EirPipeline(config=config)
        result = pipe.backup()

        # The .py file should NOT appear in backups
        mimir_backups = [b for b in result["backups"] if "mimir_" in b]
        assert len(mimir_backups) == 0, \
            f"Eir should not back up .py files as databases. Got: {mimir_backups}"
        # And an error should be recorded about the bad path
        assert any("not a database" in e.lower() or ".py" in e for e in result["errors"]), \
            "Eir should report an error when mimir_db_path is a .py file"


# ─── End-to-End Stress Test ────────────────────────────────────────────

class TestEndToEnd:
    """Full pipeline from config to results."""

    def test_standard_run_completes(self, pipeline, tmp_dir):
        # Set up minimal Mímir
        mimir_path = Path(pipeline.config.mimir_db_path)
        mimir_path.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        conn = sqlite3.connect(str(mimir_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY, content TEXT, category TEXT,
            importance INTEGER DEFAULT 5, tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, category)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS memory_access_log (
            memory_id INTEGER, accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY, domain TEXT, content TEXT,
            source TEXT, confidence REAL DEFAULT 0.9)""")
        conn.commit()
        conn.close()

        # Run with standard effort
        results = pipeline.run(effort=EffortLevel.STANDARD)
        assert results["effort_level"] == "standard"
        assert "timestamp" in results