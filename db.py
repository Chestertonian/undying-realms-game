"""
Shared database pool.

Held as module-level state rather than passed explicitly, per design
discussion — simpler call signatures throughout the codebase, acceptable
at this project's scale (single instance, one pool, no multi-tenant
concerns).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

_pool: asyncpg.Pool | None = None

DSN = os.environ.get("MUD_DATABASE_URL", "postgresql://localhost/undying")


async def _init_connection(conn: asyncpg.Connection) -> None:
    # asyncpg does not decode JSONB to dict/list by default; register a
    # codec so callers get real Python objects back, not raw JSON text.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool() -> None:
    """Create the pool. Call once at server startup before anything else
    touches the database."""
    global _pool
    if _pool is not None:
        return  # already initialized; avoid clobbering on accidental re-call
    _pool = await asyncpg.create_pool(dsn=DSN, init=_init_connection)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized — call init_pool() first.")
    return _pool