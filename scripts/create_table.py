
"""Create the discussion-board tables in MySQL."""

import sys

import mysql.connector
from mysql.connector import Error

from discussion_board.settings import ensure_settings


TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS courses (
        course_id INT AUTO_INCREMENT PRIMARY KEY,
        department VARCHAR(10) NOT NULL,
        course_number VARCHAR(10) NOT NULL,
        name VARCHAR(100) NOT NULL
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS discussions (
        discussion_id INT AUTO_INCREMENT PRIMARY KEY,
        course_id INT NOT NULL,
        title VARCHAR(200) NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        prompt TEXT NOT NULL,
        CONSTRAINT fk_discussions_course
            FOREIGN KEY (course_id)
            REFERENCES courses(course_id)
            ON DELETE CASCADE
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS posts (
        post_id INT AUTO_INCREMENT PRIMARY KEY,
        discussion_id INT NOT NULL,
        author_name VARCHAR(100) NOT NULL,
        body TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_posts_discussion
            FOREIGN KEY (discussion_id)
            REFERENCES discussions(discussion_id)
            ON DELETE CASCADE
    ) ENGINE=InnoDB
    """,
)


def main() -> None:
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
        cursor = connection.cursor()
        try:
            for statement in TABLE_STATEMENTS:
                cursor.execute(statement)
            connection.commit()
        finally:
            cursor.close()
        print("Discussion-board tables are ready.")
    except Error as exc:
        connection.rollback()
        print(f"Could not create tables: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
    