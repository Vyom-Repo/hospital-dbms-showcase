"""
Database connection pool management using asyncpg.
All database interaction uses raw SQL — no ORM.
"""

import asyncpg
import os

# ─── Configuration ───────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "vyom"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "hms_db"),
    "min_size": int(os.getenv("DB_POOL_MIN", "5")),
    "max_size": int(os.getenv("DB_POOL_MAX", "20")),
}

# ─── Global pool reference ──────────────────────────────────────────────────
_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the connection pool. Called once at application startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        min_size=DB_CONFIG["min_size"],
        max_size=DB_CONFIG["max_size"],
        # Set default search_path so all queries resolve to hms schema
        server_settings={"search_path": "hms, public"},
    )
    return _pool


async def close_pool():
    """Gracefully close the pool. Called at application shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the active connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool
