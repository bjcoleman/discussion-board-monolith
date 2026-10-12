
"""MySQL storage layer for the classroom discussion board."""

from contextlib import contextmanager
from typing import Any, Iterator

import mysql.connector
from mysql.connector import Error

from discussion_board.settings import ensure_settings


class DatabaseUnavailableError(Exception):
    """Raised when the database cannot be reached or queried."""


class CourseNotFoundError(Exception):
    """Raised when a requested course does not exist."""


class DiscussionNotFoundError(Exception):
    """Raised when a requested discussion does not exist."""


class DiscussionStorage:
    """Stores and retrieves courses, discussions, and posts in MySQL."""

    def __init__(self, settings: dict[str, str] | None = None):
        self._settings = settings or ensure_settings()

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        """Open a connection and reliably close it after an operation."""
        connection = None
        try:
            connection = mysql.connector.connect(
                host=self._settings["MYSQL_HOST"],
                port=int(self._settings["MYSQL_PORT"]),
                database=self._settings["MYSQL_DATABASE"],
                user=self._settings["MYSQL_USER"],
                password=self._settings["MYSQL_PASSWORD"],
                connection_timeout=5,
            )
            yield connection
        except Error as exc:
            raise DatabaseUnavailableError(
                f"Database operation failed: {exc}"
            ) from exc
        finally:
            if connection is not None and connection.is_connected():
                connection.close()

    def ping(self) -> None:
        """Check that MySQL and the configured database are reachable."""
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                cursor.close()

    def list_courses(self) -> list[dict[str, Any]]:
        """Return all courses ordered by department and course number."""
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT course_id, department, course_number, name
                    FROM courses
                    ORDER BY department, course_number
                    """
                )
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        """Return one course, or None if it does not exist."""
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT course_id, department, course_number, name
                    FROM courses
                    WHERE course_id = %s
                    """,
                    (course_id,),
                )
                return cursor.fetchone()
            finally:
                cursor.close()

    def add_course(
        self,
        department: str,
        course_number: str,
        name: str,
    ) -> int:
        """Insert a course and return its generated ID."""
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO courses (department, course_number, name)
                    VALUES (%s, %s, %s)
                    """,
                    (department, course_number, name),
                )
                course_id = cursor.lastrowid
                connection.commit()
                return int(course_id)
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def list_discussions(
        self, course_id: int | None = None
    ) -> list[dict[str, Any]]:
        """List discussions, including course details and reply counts.

        If course_id is supplied, only discussions for that course are
        returned. Newest discussions appear first.
        """
        query = """
            SELECT
                d.discussion_id,
                d.course_id,
                c.department,
                c.course_number,
                c.name AS course_name,
                d.title,
                d.prompt,
                d.created_at,
                COUNT(p.post_id) AS post_count
            FROM discussions AS d
            JOIN courses AS c ON c.course_id = d.course_id
            LEFT JOIN posts AS p ON p.discussion_id = d.discussion_id
        """
        parameters: tuple[Any, ...] = ()

        if course_id is not None:
            query += " WHERE d.course_id = %s"
            parameters = (course_id,)

        query += """
            GROUP BY
                d.discussion_id, d.course_id, c.department,
                c.course_number, c.name, d.title, d.prompt, d.created_at
            ORDER BY d.created_at DESC, d.discussion_id DESC
        """

        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(query, parameters)
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_discussion(
        self, discussion_id: int
    ) -> dict[str, Any] | None:
        """Return discussion details, including course details and replies.

        Returns None when the discussion does not exist. An existing
        discussion with no replies has an empty posts list.
        """
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    """
                    SELECT
                        d.discussion_id,
                        d.course_id,
                        c.department,
                        c.course_number,
                        c.name AS course_name,
                        d.title,
                        d.prompt,
                        d.created_at
                    FROM discussions AS d
                    JOIN courses AS c ON c.course_id = d.course_id
                    WHERE d.discussion_id = %s
                    """,
                    (discussion_id,),
                )
                discussion = cursor.fetchone()

                if discussion is None:
                    return None

                cursor.execute(
                    """
                    SELECT post_id, discussion_id, author_name, body,
                           created_at
                    FROM posts
                    WHERE discussion_id = %s
                    ORDER BY created_at ASC, post_id ASC
                    """,
                    (discussion_id,),
                )
                discussion["posts"] = cursor.fetchall()
                return discussion
            finally:
                cursor.close()

    def add_discussion(
        self,
        course_id: int,
        title: str,
        prompt: str,
    ) -> int:
        """Create a discussion and return its generated ID."""
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT course_id FROM courses WHERE course_id = %s",
                    (course_id,),
                )
                if cursor.fetchone() is None:
                    raise CourseNotFoundError(
                        f"Course {course_id} does not exist."
                    )

                cursor.execute(
                    """
                    INSERT INTO discussions (course_id, title, prompt)
                    VALUES (%s, %s, %s)
                    """,
                    (course_id, title, prompt),
                )
                discussion_id = cursor.lastrowid
                connection.commit()
                return int(discussion_id)
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def list_posts(
        self, discussion_id: int
    ) -> list[dict[str, Any]]:
        """Return replies for a discussion, oldest first."""
        with self._connection() as connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT discussion_id FROM discussions "
                    "WHERE discussion_id = %s",
                    (discussion_id,),
                )
                if cursor.fetchone() is None:
                    raise DiscussionNotFoundError(
                        f"Discussion {discussion_id} does not exist."
                    )

                cursor.execute(
                    """
                    SELECT post_id, discussion_id, author_name, body,
                           created_at
                    FROM posts
                    WHERE discussion_id = %s
                    ORDER BY created_at ASC, post_id ASC
                    """,
                    (discussion_id,),
                )
                return cursor.fetchall()
            finally:
                cursor.close()

    def add_post(
        self,
        discussion_id: int,
        author_name: str,
        body: str,
    ) -> int:
        """Add a reply and return its generated ID."""
        with self._connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT discussion_id FROM discussions "
                    "WHERE discussion_id = %s",
                    (discussion_id,),
                )
                if cursor.fetchone() is None:
                    raise DiscussionNotFoundError(
                        f"Discussion {discussion_id} does not exist."
                    )

                cursor.execute(
                    """
                    INSERT INTO posts (discussion_id, author_name, body)
                    VALUES (%s, %s, %s)
                    """,
                    (discussion_id, author_name, body),
                )
                post_id = cursor.lastrowid
                connection.commit()
                return int(post_id)
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
                