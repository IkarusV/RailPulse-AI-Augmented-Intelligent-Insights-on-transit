import re

import sqlparse
from sqlparse.tokens import Comment, DDL, DML, Keyword


ALLOWED_TABLES = {"departures"}
FORBIDDEN_WORDS = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "execute",
    "insert",
    "intersect",
    "join",
    "load_extension",
    "merge",
    "pragma",
    "replace",
    "reindex",
    "truncate",
    "union",
    "update",
    "vacuum",
}


class UnsafeQuery(ValueError):
    """Raised when generated SQL breaks the read-only query policy."""

    pass


# Step 1: validate one generated SQL statement

def validate_sql(sql):
    """Accept a small read-only query or reject it before execution.

    Input:
        sql: query proposed by the language model.
    Returns:
        Normalized SELECT query with a safe row limit.
    """

    candidate = sql.strip()
    if not candidate:
        raise UnsafeQuery("The generated query is empty")
    if len(candidate) > 4_000:
        raise UnsafeQuery("The generated query is too long")
    if "--" in candidate or "/*" in candidate or "*/" in candidate:
        raise UnsafeQuery("SQL comments are not allowed")

    # Separate stacked statements and inspect their SQL token types.
    statements = [statement for statement in sqlparse.parse(candidate) if str(statement).strip()]
    if len(statements) != 1:
        raise UnsafeQuery("Exactly one SQL statement is allowed")

    statement = statements[0]
    first_word = statement.token_first(skip_cm=True).value.upper()
    if first_word != "SELECT":
        raise UnsafeQuery("Only SELECT queries are allowed")

    for token in statement.flatten():
        if token.ttype in Comment:
            raise UnsafeQuery("SQL comments are not allowed")
        value = token.value.lower()
        if value in FORBIDDEN_WORDS:
            raise UnsafeQuery(f"Forbidden SQL operation: {value.upper()}")
        if token.ttype in DDL:
            raise UnsafeQuery("DDL statements are forbidden")
        if token.ttype in DML and value != "select":
            raise UnsafeQuery("Only SELECT queries are allowed")
        if token.ttype in Keyword and value in FORBIDDEN_WORDS:
            raise UnsafeQuery(f"Forbidden SQL operation: {value.upper()}")

    # The assistant only needs explicit fields from one prepared table.
    if re.search(r"\bselect\s+\*", candidate, flags=re.IGNORECASE):
        raise UnsafeQuery("SELECT * is not allowed")

    if len(re.findall(r"\bfrom\b", candidate, flags=re.IGNORECASE)) != 1:
        raise UnsafeQuery("The query must contain exactly one FROM clause")

    table_names = re.findall(
        r"\bfrom\s+([A-Za-z_][A-Za-z0-9_]*)",
        candidate,
        flags=re.IGNORECASE,
    )
    if not table_names:
        raise UnsafeQuery("The query must read from the departures view")
    unknown = {name.lower() for name in table_names} - ALLOWED_TABLES
    if unknown:
        raise UnsafeQuery(f"Unknown or forbidden table: {sorted(unknown)[0]}")

    # Add a default cap when the model forgot one.
    if not re.search(r"\blimit\s+\d+\b", candidate, flags=re.IGNORECASE):
        candidate = candidate.rstrip("; ") + " LIMIT 100"
    else:
        match = re.search(r"\blimit\s+(\d+)\b", candidate, flags=re.IGNORECASE)
        if match and int(match.group(1)) > 100:
            raise UnsafeQuery("The query row limit cannot exceed 100")

    return candidate
