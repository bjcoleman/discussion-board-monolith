import pytest
from unittest.mock import MagicMock
from discussion_board.app import create_app
from discussion_board.db import CourseNotFoundError, DatabaseUnavailableError
from unittest.mock import MagicMock

def test_index():
    app = create_app(MagicMock())
    

@pytest.fixture
def mock_storage():
    """Create a mock DiscussionStorage instance."""
    storage = MagicMock()
    return storage


@pytest.fixture
def client(mock_storage):
    """Flask test client fixture."""
    app = create_app(mock_storage)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# --- Tests for POST /courses Validation ---

def test_create_course_success(client, mock_storage):
    mock_storage.add_course.return_value = 1
    res = client.post(
        "/courses",
        json={"department": "CSCI", "courseNumber": "390", "name": "Cloud Computing"},
    )
    assert res.status_code == 201
    assert res.get_json() == {"id": 1}


def test_create_course_rejects_non_json(client):
    res = client.post("/courses", data="not json", content_type="text/plain")
    assert res.status_code == 400
    assert "Content-Type must be application/json" in res.get_json()["error"]["message"]


def test_create_course_rejects_whitespace_only(client):
    res = client.post(
        "/courses",
        json={"department": "   ", "courseNumber": "390", "name": "Cloud Computing"},
    )
    assert res.status_code == 400
    assert "department" in res.get_json()["error"]["message"]


def test_create_course_rejects_oversized_fields(client):
    res = client.post(
        "/courses",
        json={
            "department": "CSCI_TOO_LONG",
            "courseNumber": "390",
            "name": "Cloud Computing",
        },
    )
    assert res.status_code == 400


# --- Tests for POST /discussions Validation ---

def test_create_discussion_rejects_invalid_course_id_type(client):
    # Sending string instead of integer
    res = client.post(
        "/discussions",
        json={"courseId": "1", "title": "Valid Title", "prompt": "Valid Prompt"},
    )
    assert res.status_code == 400
    assert "courseId must be a positive integer" in res.get_json()["error"]["message"]


def test_create_discussion_handles_course_not_found(client, mock_storage):
    mock_storage.add_discussion.side_effect = CourseNotFoundError("Course 999 does not exist.")
    res = client.post(
        "/discussions",
        json={"courseId": 999, "title": "Valid Title", "prompt": "Valid Prompt"},
    )
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "NOT_FOUND"


# --- Tests for POST /discussions/<id>/posts Validation ---

def test_create_post_rejects_empty_body(client):
    res = client.post(
        "/discussions/1/posts",
        json={"authorName": "Alice", "body": "   "},
    )
    assert res.status_code == 400