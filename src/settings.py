
"""Load and validate database configuration."""

import os

from dotenv import load_dotenv


REQUIRED_SETTINGS = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
)


def ensure_settings() -> dict[str, str]:
    """Load required settings from the environment or .env file."""
    load_dotenv()

    missing = [
        name for name in REQUIRED_SETTINGS
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Missing required settings in the environment / .env: "
            + ", ".join(missing)
        )

    settings = {
        name: os.environ[name]
        for name in REQUIRED_SETTINGS
    }

    try:
        port = int(settings["MYSQL_PORT"])
    except ValueError as exc:
        raise RuntimeError("MYSQL_PORT must be an integer.") from exc

    if not 1 <= port <= 65535:
        raise RuntimeError("MYSQL_PORT must be between 1 and 65535.")

    settings["MYSQL_PORT"] = str(port)
    return settings
    