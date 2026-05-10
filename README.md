# Eir

> *Eir is the best of physicians. She sits at Lyfjaberg, the Hill of Healing.*

**Version 1.0.0** · Norse-themed · MIT License

---

Eir is a SQLite backup and health-check library for **Runa's memory systems**. Named after the Norse goddess of healing and medicine, Eir keeps your memory backends healthy through automated backups with rotation, integrity verification, and self-healing pipelines.

## What It Does

Eir runs a **consolidation pipeline** that maintains the health of three memory backends:

1. **Decay** — Applies Ebbinghaus forgetting: reduces importance of rarely-accessed memories over time
2. **Promotion** — Elevates high-importance, frequently-accessed memories into durable knowledge
3. **Deduplication** — Finds and merges exact-duplicate memories, keeping the strongest copy
4. **Consolidation** — Strengthens Hebbian connections that have proven their worth through repeated co-activation
5. **Backup** — Creates timestamped `.db` backups with automatic rotation (keeps the N most recent)
6. **Integrity Check** — Diagnoses corruption: FTS integrity, orphaned records, total memory counts

All steps are individually toggleable and the full pipeline returns a structured results dict for observability.

## Install

```bash
pip install eir
```

With optional backends:

```bash
pip install eir[muninn]    # Hebbian memory backend
pip install eir[huginn]    # Vector memory backend
```

Dev dependencies:

```bash
pip install eir[dev]       # pytest, pytest-cov
```

## Quick Start

```python
from eir import EirPipeline, EirConfig

# Use defaults or customize
config = EirConfig(
    mimir_db_path="~/.hermes/memory/runa_memory.db",
    backup_dir="~/.hermes/memory/backups",
    max_backups=7,
    decay_enabled=True,
    integrity_check_enabled=True,
)

pipeline = EirPipeline(config=config)

# Run the full consolidation pipeline
results = pipeline.run()

# Or run individual steps
pipeline.backup()            # Timestamped backups with rotation
pipeline.integrity_check()   # Diagnose all backends
pipeline.decay()              # Ebbinghaus forgetting
pipeline.promote()            # Promote important memories
pipeline.deduplicate()        # Merge duplicates
pipeline.consolidate()        # Strengthen Hebbian paths

# Quick health check
health = pipeline.health()

# Always close when done (releases all connections)
pipeline.close()
```

## Configuration

All settings live in the `EirConfig` dataclass:

**Memory Backends**
- `mimir_db_path` — Path to the Mímir SQLite database (default: `~/.hermes/memory/runa_memory.py`)
- `muninn_db_path` — Path to Muninn Hebbian database
- `huginn_url` — Huginn vector store URL (default: `http://localhost:6333`)

**Pipeline Controls**
- `decay_enabled` / `decay_days` — Toggle Ebbinghaus decay; days per cycle (default: 1.0)
- `promotion_enabled` / `promotion_importance_threshold` — Toggle promotion; minimum importance to promote (default: 7)
- `dedup_enabled` / `dedup_similarity_threshold` — Toggle dedup; cosine similarity threshold (default: 0.85)
- `consolidation_enabled` / `consolidation_strength_threshold` — Toggle Hebbian consolidation; minimum strength (default: 0.6)
- `backup_enabled` / `backup_dir` / `max_backups` — Toggle backups; backup directory; rotation limit (default: 7)
- `integrity_check_enabled` — Toggle integrity verification

## Backup Details

Backups are timestamped copies of all memory databases:

```
~/.hermes/memory/backups/
├── mimir_20260510_120000.db
├── mimir_20260509_120000.db
├── muninn_20260510_120000.db
└── muninn_20260509_120000.db
```

Old backups beyond `max_backups` are automatically removed during rotation. Each backup is a `shutil.copy2` — preserving metadata — making recovery a simple file copy.

## Resource Management

Eir manages connections to three backends lazily and **must be closed** when done:

```python
pipeline = EirPipeline(config)
# ... work ...
pipeline.close()  # Releases Mímir, Muninn, and Huginn connections
```

Connections are created on first access and reused across the pipeline's lifetime. `close()` properly tears down all of them, preventing resource leaks.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT · Authors: Runa Gridweaver, Volmarr Viking