import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from database import execute_readonly
from llm_client import summarize_result
from sql_guard import validate_sql


OUTPUT_PATH = BASE_DIR / "reports" / "executive_brief.md"

ANOMALY_SQL = """
SELECT
    vehicle_id,
    train_class,
    destination_name,
    platform,
    scheduled_time,
    delay_minutes
FROM departures
ORDER BY delay_seconds DESC
LIMIT 5
"""


# Step 1: query the five largest observed delays

def main():
    """Generate a Markdown operations brief from validated database rows."""

    sql = validate_sql(ANOMALY_SQL)
    columns, rows = execute_readonly(sql)

    # Step 2: summarize only the rows returned by the query.
    brief = summarize_result(
        "Write a concise executive briefing on the five most delayed departures.",
        sql,
        columns,
        rows,
    )
    # Step 3: save the finished brief for review or sharing.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "# RailPulse Executive Brief\n\n" + brief + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT_PATH.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
