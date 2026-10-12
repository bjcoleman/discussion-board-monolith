
"""Load data/sample-data.sql into the development database."""

import argparse
import sys
from pathlib import Path

import mysql.connector
from mysql.connector import Error

from discussion_board.settings import ensure_settings


ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = ROOT / "data" / "sample-data.sql"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load the discussion-board sample data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing rows before loading sample data.",
    )
    args = parser.parse_args()

    try:
        settings = ensure_settings()
        connection = mysql.connector.connect(
            host=settings["MYSQL_HOST"],
            port=int(settings["MYSQL_PORT"]),
            database=settings["MYSQL_DATABASE"],
            user=settings["MYSQL_USER"],
            password=settings["MYSQL_PASSWORD"],
            connection_timeout=5,
        )
    except (RuntimeError, Error) as exc:
        print(f"Could not connect to MySQL: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        sql_text = SAMPLE_DATA_PATH.read_text(encoding="utf-8")
        statements = [
            statement.strip()
            for statement in sql_text.split(";")
            if statement.strip()
        ]

        cursor = connection.cursor()
        try:
            if args.reset:
                cursor.execute("DELETE FROM posts")
                cursor.execute("DELETE FROM discussions")
                cursor.execute("DELETE FROM courses")

            for statement in statements:
                cursor.execute(statement)

            connection.commit()
        finally:
            cursor.close()

        print(f"Loaded sample data from {SAMPLE_DATA_PATH}.")
    except (OSError, Error) as exc:
        connection.rollback()
        print(f"Could not load sample data: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
    