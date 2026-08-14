import csv
import sqlite3
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_CSV = (
    BASE_DIR.parent
    / "railpulse-powerbi-dashboard"
    / "data"
    / "fact_departures_latest.csv"
)
SNAPSHOT_URL = "https://raw.githubusercontent.com/IkarusV/railpulse-powerbi-dashboard/main/data/fact_departures_latest.csv"
DATABASE_PATH = BASE_DIR / "data" / "railpulse_chatbot.db"


SCHEMA = """
CREATE TABLE departures (
    departure_key TEXT PRIMARY KEY,
    station_id TEXT NOT NULL,
    station_name TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    train_number TEXT NOT NULL,
    train_class TEXT NOT NULL,
    destination_name TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    scheduled_hour INTEGER NOT NULL,
    delay_seconds INTEGER NOT NULL CHECK (delay_seconds >= 0),
    delay_minutes REAL NOT NULL CHECK (delay_minutes >= 0),
    platform TEXT,
    is_canceled INTEGER NOT NULL CHECK (is_canceled IN (0, 1)),
    collected_at TEXT NOT NULL,
    observation_count INTEGER NOT NULL CHECK (observation_count >= 1)
);

CREATE INDEX idx_departures_platform ON departures (platform);
CREATE INDEX idx_departures_train_class ON departures (train_class);
CREATE INDEX idx_departures_scheduled_hour ON departures (scheduled_hour);
CREATE INDEX idx_departures_delay ON departures (delay_seconds);
"""


# Step 1: locate or download the departure snapshot

def build_database():
    """Build a checked SQLite database from the Power BI departure export."""

    source_path = SOURCE_CSV
    downloaded_path = BASE_DIR / "data" / "fact_departures_latest.download.csv"
    if not source_path.exists():
        downloaded_path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            SNAPSHOT_URL,
            headers={"User-Agent": "RailPulse-AI/1.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            downloaded_path.write_bytes(response.read())
        source_path = downloaded_path
        print(f"downloaded source snapshot from {SNAPSHOT_URL}")

    # Step 2: build a temporary database so failures keep the old copy.
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = DATABASE_PATH.with_suffix(".tmp.db")
    temporary_path.unlink(missing_ok=True)

    connection = sqlite3.connect(temporary_path)
    connection.executescript(SCHEMA)

    # Step 3: convert CSV strings into the schema's Python types.
    with source_path.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = []
        for row in csv.DictReader(csv_file):
            rows.append(
                (
                    row["departure_key"],
                    row["station_id"],
                    "Brussels-Central",
                    row["vehicle_id"],
                    row["train_number"],
                    row["train_class"],
                    row["destination_name"],
                    row["scheduled_time"],
                    row["scheduled_date"],
                    int(row["scheduled_hour"]),
                    int(row["delay_seconds"]),
                    float(row["delay_minutes"]),
                    row["platform"] or None,
                    1 if row["is_canceled"].lower() == "true" else 0,
                    row["collected_at"],
                    int(row["observation_count"]),
                )
            )

    # Step 4: insert in one batch and check database integrity.
    connection.executemany(
        "INSERT INTO departures VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.commit()
    connection.close()
    if integrity != "ok":
        temporary_path.unlink(missing_ok=True)
        raise SystemExit(f"Database integrity check failed: {integrity}")

    # Step 5: replace the old snapshot only after a successful check.
    DATABASE_PATH.unlink(missing_ok=True)
    temporary_path.replace(DATABASE_PATH)
    downloaded_path.unlink(missing_ok=True)
    print(f"built {DATABASE_PATH} with {len(rows)} departures; integrity: {integrity}")


def main():
    """Run the database builder from the command line."""

    build_database()


if __name__ == "__main__":
    main()
