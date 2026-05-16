from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


_pool: AsyncConnectionPool | None = None


def init_pool(database_url: str, *, min_size: int = 1, max_size: int = 10) -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row},
        open=False,
    )


async def open_pool() -> None:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    await _pool.open()


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


@asynccontextmanager
async def get_connection() -> AsyncIterator[AsyncConnection]:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.connection() as conn:
        yield conn
