
"""Wait until the MySQL server accepts connections."""

import argparse
import sys
import time

import mysql.connector
from mysql.connector import Error

from discussion_board.settings import ensure_settings


def wait_for_mysql(
    settings: dict[str, str],
    timeout_seconds: int,
) -> None:
    """Wait for MySQL to accept a connection or raise TimeoutError."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        try:
            connection = mysql.connector.connect(
                host=settings["MYSQL_HOST"],
                port=int(settings["MYSQL_PORT"]),
                user=settings["MYSQL_USER"],
                password=settings["MYSQL_PASSWORD"],
                connection_timeout=2,
            )
            connection.close()
            return
        except Error as exc:
            last_error = exc
            time.sleep(1)

    raise TimeoutError(
        f"MySQL did not become ready within {timeout_seconds} seconds. "
        f"Last error: {last_error}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wait until MySQL accepts connections."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Seconds to wait before failing (default: 60).",
    )
    args = parser.parse_args()

    try:
        settings = ensure_settings()
        wait_for_mysql(settings, args.timeout)
    except (RuntimeError, TimeoutError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print("MySQL is ready.")


if __name__ == "__main__":
    main()
    