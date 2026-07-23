"""
Database Connection Manager
Asynchronous connection pool initialization and schema path configuration.
"""

import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "vyom"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "hms_db"),
    "min_size": int(os.getenv("DB_POOL_MIN", "5")),
    "max_size": int(os.getenv("DB_POOL_MAX", "20")),
}

_pool: asyncpg.Pool | None = None


async def _init_connection(conn):
    await conn.execute("SET search_path TO hms, public;")


async def init_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        min_size=DB_CONFIG["min_size"],
        max_size=DB_CONFIG["max_size"],
        init=_init_connection,
        server_settings={"search_path": "hms, public"},
    )
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized.")
    return _pool
