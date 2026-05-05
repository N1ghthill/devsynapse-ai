import asyncio
import sqlite3

from core.async_utils import run_blocking, shutdown_blocking_executor


def test_run_blocking_does_not_use_default_executor():
    async def main():
        return await run_blocking(lambda value: value + 1, 41)

    assert asyncio.run(main()) == 42
    shutdown_blocking_executor(wait=True)


def test_run_blocking_handles_sqlite_work(tmp_path):
    def create_table():
        conn = sqlite3.connect(tmp_path / "async.db")
        conn.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        return "ok"

    async def main():
        return await run_blocking(create_table)

    assert asyncio.run(main()) == "ok"
    shutdown_blocking_executor(wait=True)
