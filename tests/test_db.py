from unittest.mock import MagicMock, patch

import pytest
from mysql.connector import Error

from discussion_board.db import (
    CourseNotFoundError,
    DatabaseUnavailableError,
    DiscussionNotFoundError,
    DiscussionStorage,
)


SETTINGS = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3306",
    "MYSQL_DATABASE": "discussion_board_test",
    "MYSQL_USER": "test_user",
    "MYSQL_PASSWORD": "test_password",
}


@pytest.fixture
def cursor():
    return MagicMock()


@pytest.fixture
def connection(cursor):
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def storage(connection):
    with patch(
        "discussion_board.db.mysql.connector.connect",
        return_value=connection,
    ) as connect:
        yield DiscussionStorage(SETTINGS), connect


def test_init_uses_provided_settings():
    storage = DiscussionStorage(SETTINGS)
    assert storage._settings == SETTINGS


@patch("discussion_board.db.ensure_settings", return_value=SETTINGS)
def test_init_loads_settings_when_omitted(ensure_settings):
    storage = DiscussionStorage()
    ensure_settings.assert_called_once_with()
    assert storage._settings == SETTINGS


def test_connection_passes_settings_to_mysql(storage, connection):
    storage_obj, connect = storage
    storage_obj.ping()

    connect.assert_called_once_with(
        host=SETTINGS["MYSQL_HOST"],
        port=int(SETTINGS["MYSQL_PORT"]),
        database=SETTINGS["MYSQL_DATABASE"],
        user=SETTINGS["MYSQL_USER"],
        password=SETTINGS["MYSQL_PASSWORD"],
        connection_timeout=5,
    )
    connection.close.assert_called_once_with()


def test_connection_wraps_mysql_errors():
    storage = DiscussionStorage(SETTINGS)
    with patch(
        "discussion_board.db.mysql.connector.connect",
        side_effect=Error("server down"),
    ):
        with pytest.raises(DatabaseUnavailableError, match="server down"):
            storage.ping()


def test_connection_skips_close_when_not_connected(storage, connection):
    storage_obj, _connect = storage
    connection.is_connected.return_value = False

    storage_obj.ping()

    connection.close.assert_not_called()


def test_ping_executes_select(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = (1,)

    storage_obj.ping()

    cursor.execute.assert_called_once_with("SELECT 1")
    cursor.fetchone.assert_called_once_with()
    cursor.close.assert_called_once_with()
    connection.cursor.assert_called_once_with()


def test_list_courses_returns_empty_list(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.fetchall.return_value = []

    assert storage_obj.list_courses() == []
    connection.cursor.assert_called_once_with(dictionary=True)
    assert "FROM courses" in cursor.execute.call_args.args[0]
    cursor.close.assert_called_once_with()


def test_list_courses_returns_rows(storage, cursor):
    storage_obj, _connect = storage
    courses = [
        {
            "course_id": 2,
            "department": "CSCI",
            "course_number": "294",
            "name": "Machine Learning",
        },
        {
            "course_id": 1,
            "department": "CSCI",
            "course_number": "390",
            "name": "Cloud Computing",
        },
    ]
    cursor.fetchall.return_value = courses

    assert storage_obj.list_courses() == courses


def test_get_course_returns_none_when_missing(storage, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = None

    assert storage_obj.get_course(99) is None
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (99,)


def test_get_course_returns_row_when_found(storage, cursor):
    storage_obj, _connect = storage
    course = {
        "course_id": 1,
        "department": "CSCI",
        "course_number": "390",
        "name": "Cloud Computing",
    }
    cursor.fetchone.return_value = course

    assert storage_obj.get_course(1) == course


def test_add_course_commits_and_returns_id(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.lastrowid = 12

    course_id = storage_obj.add_course("CSCI", "390", "Cloud Computing")

    assert course_id == 12
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (
        "CSCI",
        "390",
        "Cloud Computing",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    cursor.close.assert_called_once_with()


def test_add_course_rolls_back_on_failure(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.execute.side_effect = Error("insert failed")

    with pytest.raises(DatabaseUnavailableError, match="insert failed"):
        storage_obj.add_course("CSCI", "390", "Cloud Computing")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    cursor.close.assert_called_once_with()


def test_list_discussions_includes_zero_and_nonzero_post_counts(
    storage, cursor
):
    storage_obj, _connect = storage
    cursor.fetchall.return_value = [
        {"discussion_id": 1, "title": "Question about EC2", "post_count": 2},
        {"discussion_id": 2, "title": "Question about HW01", "post_count": 0},
    ]

    rows = storage_obj.list_discussions()

    assert [row["post_count"] for row in rows] == [2, 0]
    query = cursor.execute.call_args.args[0]
    assert "COUNT(p.post_id) AS post_count" in query
    assert "LEFT JOIN posts" in query
    assert cursor.execute.call_args.args[1] == ()


def test_list_discussions_filters_by_course_and_can_be_empty(
    storage, cursor
):
    storage_obj, _connect = storage
    cursor.fetchall.return_value = []

    assert storage_obj.list_discussions(course_id=7) == []

    query, parameters = cursor.execute.call_args.args
    assert "WHERE d.course_id = %s" in query
    assert parameters == (7,)


def test_get_discussion_returns_none_when_missing(storage, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = None

    assert storage_obj.get_discussion(404) is None
    assert cursor.fetchall.call_count == 0
    assert cursor.execute.call_args.args[1] == (404,)


def test_get_discussion_returns_empty_posts_list(storage, cursor):
    storage_obj, _connect = storage
    discussion = {
        "discussion_id": 2,
        "course_id": 1,
        "title": "Question about HW01",
        "prompt": "Any suggestions?",
    }
    cursor.fetchone.return_value = discussion
    cursor.fetchall.return_value = []

    result = storage_obj.get_discussion(2)

    assert result["posts"] == []
    assert result["discussion_id"] == 2
    assert cursor.execute.call_count == 2


def test_get_discussion_includes_posts_in_order(storage, cursor):
    storage_obj, _connect = storage
    discussion = {
        "discussion_id": 1,
        "course_id": 1,
        "title": "Question about EC2",
    }
    posts = [
        {"post_id": 1, "author_name": "Connor", "body": "Same instance."},
        {"post_id": 2, "author_name": "Aidan", "body": "Agreed."},
    ]
    cursor.fetchone.return_value = discussion
    cursor.fetchall.return_value = posts

    result = storage_obj.get_discussion(1)

    assert result["posts"] == posts
    posts_query = cursor.execute.call_args_list[1].args[0]
    assert "ORDER BY created_at ASC, post_id ASC" in posts_query
    assert cursor.execute.call_args_list[1].args[1] == (1,)


def test_add_discussion_raises_when_course_is_missing(
    storage, connection, cursor
):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = None

    with pytest.raises(CourseNotFoundError, match="Course 99 does not exist"):
        storage_obj.add_discussion(99, "Title", "Prompt")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    insert_calls = [
        call
        for call in cursor.execute.call_args_list
        if "INSERT INTO discussions" in call.args[0]
    ]
    assert insert_calls == []


def test_add_discussion_commits_and_returns_id(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = (1,)
    cursor.lastrowid = 5

    discussion_id = storage_obj.add_discussion(
        1, "Question about EC2", "How does it fit?"
    )

    assert discussion_id == 5
    connection.commit.assert_called_once_with()
    insert_call = cursor.execute.call_args_list[1]
    assert "INSERT INTO discussions" in insert_call.args[0]
    assert insert_call.args[1] == (1, "Question about EC2", "How does it fit?")


def test_list_posts_raises_when_discussion_is_missing(storage, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = None

    with pytest.raises(
        DiscussionNotFoundError, match="Discussion 404 does not exist"
    ):
        storage_obj.list_posts(404)

    assert cursor.fetchall.call_count == 0


def test_list_posts_returns_empty_list_for_discussion_with_no_replies(
    storage, cursor
):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = (2,)
    cursor.fetchall.return_value = []

    assert storage_obj.list_posts(2) == []
    posts_query = cursor.execute.call_args_list[1].args[0]
    assert "FROM posts" in posts_query
    assert cursor.execute.call_args_list[1].args[1] == (2,)


def test_list_posts_returns_replies(storage, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = (1,)
    posts = [
        {"post_id": 1, "author_name": "Connor", "body": "Same instance."},
        {"post_id": 2, "author_name": "Aidan", "body": "Agreed."},
    ]
    cursor.fetchall.return_value = posts

    assert storage_obj.list_posts(1) == posts


def test_add_post_raises_when_discussion_is_missing(
    storage, connection, cursor
):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = None

    with pytest.raises(
        DiscussionNotFoundError, match="Discussion 404 does not exist"
    ):
        storage_obj.add_post(404, "Connor", "Hello")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_add_post_commits_and_returns_id(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = (1,)
    cursor.lastrowid = 8

    post_id = storage_obj.add_post(1, "Connor", "Same instance.")

    assert post_id == 8
    connection.commit.assert_called_once_with()
    insert_call = cursor.execute.call_args_list[1]
    assert "INSERT INTO posts" in insert_call.args[0]
    assert insert_call.args[1] == (1, "Connor", "Same instance.")


def test_add_post_rolls_back_when_insert_fails(storage, connection, cursor):
    storage_obj, _connect = storage
    cursor.fetchone.return_value = (1,)

    def execute(query, params=None):
        if "INSERT INTO posts" in query:
            raise Error("insert failed")

    cursor.execute.side_effect = execute

    with pytest.raises(DatabaseUnavailableError, match="insert failed"):
        storage_obj.add_post(1, "Connor", "Same instance.")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    cursor.close.assert_called_once_with()
