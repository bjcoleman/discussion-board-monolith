
"""Drop discussion-board tables. This permanently deletes their data."""

import argparse
import sys

import mysql.connector
from mysql.connector import Error

from discussion_board.settings import ensure_settings


TABLES = ("posts", "discussions", "courses")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drop the discussion-board tables."
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Drop tables without prompting for confirmation.",
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
        if not args.yes:
            answer = input(
                f"Drop all discussion-board tables in "
                f"{settings['MYSQL_DATABASE']!r}? This deletes all data. [y/N] "
            ).strip().lower()
            if answer not in ("y", "yes"):
                print("Cancelled.")
                return

        cursor = connection.cursor()
        try:
            for table in TABLES:
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            connection.commit()
        finally:
            cursor.close()

        print("Dropped discussion-board tables.")
    except Error as exc:
        connection.rollback()
        print(f"Could not drop tables: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
    