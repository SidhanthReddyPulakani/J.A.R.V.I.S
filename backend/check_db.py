from jarvis.storage.database import Database
from jarvis.core.config import DATA_DIR


def main():
    db_path = DATA_DIR / "jarvis.db"

    print("DATABASE:", db_path)
    print()

    db = Database(db_path)
    db.initialize()

    tables = db.fetch_all(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    )

    print("TABLES:")
    for row in tables:
        print(" -", row[0])

    for table in ["agent_state", "conversations", "messages"]:
        print(f"\n--- {table} ---")

        rows = db.fetch_all(
            f"PRAGMA table_info({table})"
        )

        for row in rows:
            print(row)


if __name__ == "__main__":
    main()