from core.db import DEFAULT_SQLITE_BUSY_TIMEOUT_MS, connect_db


def test_connect_db_applies_runtime_pragmas(tmp_path):
    db_path = tmp_path / "runtime.db"

    conn = connect_db(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA busy_timeout")
    busy_timeout = cursor.fetchone()[0]
    cursor.execute("PRAGMA foreign_keys")
    foreign_keys = cursor.fetchone()[0]
    cursor.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]
    conn.close()

    assert busy_timeout == DEFAULT_SQLITE_BUSY_TIMEOUT_MS
    assert foreign_keys == 1
    assert journal_mode == "wal"


def test_connect_db_returns_rows_by_name(tmp_path):
    conn = connect_db(tmp_path / "rows.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE example (name TEXT)")
    cursor.execute("INSERT INTO example (name) VALUES ('devsynapse')")
    cursor.execute("SELECT name FROM example")
    row = cursor.fetchone()
    conn.close()

    assert row["name"] == "devsynapse"
