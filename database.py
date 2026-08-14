import sqlite3

from config import DATABASE_PATH, QUERY_ROW_LIMIT


class DatabaseError(RuntimeError):
    """Raised when the snapshot cannot execute a safe query."""

    pass


# Step 1: execute validated SQL through a read-only connection

def execute_readonly(sql):
    """Run one validated query against the departure snapshot.

    Input:
        sql: SELECT query already accepted by sql_guard.py.
    Returns:
        Column names and rows, capped by QUERY_ROW_LIMIT.
    """

    if not DATABASE_PATH.exists():
        raise DatabaseError("Database snapshot not found. Run scripts/build_database.py")

    # URI mode prevents writes at the SQLite connection level.
    uri = f"file:{DATABASE_PATH.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=10)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        # Stop expensive generated queries after roughly one million VM steps.
        remaining_checks = 10_000

        def query_budget():
            nonlocal remaining_checks
            remaining_checks -= 1
            return remaining_checks <= 0

        connection.set_progress_handler(query_budget, 100)
        cursor = connection.execute(sql)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchmany(QUERY_ROW_LIMIT + 1)
    except sqlite3.Error as error:
        raise DatabaseError(f"Query execution failed: {error}") from error
    finally:
        if "connection" in locals():
            connection.close()

    if len(rows) > QUERY_ROW_LIMIT:
        raise DatabaseError(f"Query returned more than {QUERY_ROW_LIMIT} rows")
    return columns, [list(row) for row in rows]
