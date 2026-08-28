"""Shared JSON key-value store used by every per-category mock backend.

The task schema (``tasks/schema.json`` / :mod:`autobench.schema`) does not carry
tabular ``database_schemas``; each task's ``context.initial_state`` is a nested
JSON object whose top-level keys differ from task to task even within one
category. Rather than model ~20 heterogeneous shapes as SQL tables, every
backend seeds a single ``kv_state(key, value)`` table where ``value`` is a JSON
blob, one row per top-level key of ``initial_state``.

Determinism: the session brief references ``initial_state_seed`` / a
``random.Random`` for id generation, but that field does not exist in the
schema. Synthetic ids come from ``_id_counter`` — an integer persisted in the
same table and bumped per call — which is strictly deterministic across replays.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

_TABLE = "kv_state"
_COUNTER_KEY = "_id_counter"
_FALLBACK_NOW = "2026-01-01T00:00:00Z"


def initialize_kv(db_conn: sqlite3.Connection, initial_state: dict[str, Any]) -> None:
    """Create the ``kv_state`` table and seed it from ``initial_state``."""
    db_conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_TABLE} (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    db_conn.execute(f"DELETE FROM {_TABLE}")
    for key, value in initial_state.items():
        db_conn.execute(
            f"INSERT INTO {_TABLE} (key, value) VALUES (?, ?)", (key, json.dumps(value))
        )
    db_conn.execute(
        f"INSERT OR REPLACE INTO {_TABLE} (key, value) VALUES (?, ?)", (_COUNTER_KEY, "0")
    )
    db_conn.commit()


def load(db_conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = db_conn.execute(f"SELECT value FROM {_TABLE} WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return json.loads(row[0])


def load_dict(db_conn: sqlite3.Connection, key: str) -> dict[Any, Any]:
    value = load(db_conn, key, {})
    return value if isinstance(value, dict) else {}


def load_list(db_conn: sqlite3.Connection, key: str) -> list[Any]:
    value = load(db_conn, key, [])
    return value if isinstance(value, list) else []


def save(db_conn: sqlite3.Connection, key: str, value: Any) -> None:
    db_conn.execute(
        f"INSERT OR REPLACE INTO {_TABLE} (key, value) VALUES (?, ?)",
        (key, json.dumps(value)),
    )
    db_conn.commit()


def append(db_conn: sqlite3.Connection, key: str, item: Any) -> list[Any]:
    """Append ``item`` to the JSON list at ``key`` (created if absent)."""
    seq = load_list(db_conn, key)
    seq.append(item)
    save(db_conn, key, seq)
    return seq


def patch_item(
    db_conn: sqlite3.Connection,
    container_key: str,
    item_key: Any,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Merge ``patch`` into ``container[item_key]`` (dict-of-dicts) and persist."""
    container = load_dict(db_conn, container_key)
    current = container.get(item_key)
    merged: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    merged.update(patch)
    container[item_key] = merged
    save(db_conn, container_key, container)
    return merged


def get_item(
    db_conn: sqlite3.Connection,
    container_key: str,
    item_key: Any,
    default: Any = None,
) -> Any:
    return load_dict(db_conn, container_key).get(item_key, default)


def next_id(db_conn: sqlite3.Connection, prefix: str) -> str:
    n = int(load(db_conn, _COUNTER_KEY, 0)) + 1
    save(db_conn, _COUNTER_KEY, n)
    return f"{prefix}_{n:05d}"


def now(db_conn: sqlite3.Connection) -> str:
    value = load(db_conn, "now", None)
    return value if isinstance(value, str) else _FALLBACK_NOW


def table_names(db_conn: sqlite3.Connection) -> list[str]:
    rows = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [str(r[0]) for r in rows]
