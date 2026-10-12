import sys
from flask import Flask, jsonify, render_template, request

from board.db import DatabaseUnavailableError, BoardStorage
from board.service import (
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
    DiscussionBoardApp,
)


def _error(code: str, message: str, status: int):
    """Format standard API error response matching OpenAPI specs."""
    return jsonify({"error": {"code": code, "message": message}}), status


def _course_json(course) -> dict:
    """Serialize Course schema object."""
    return {
        "id": course.id,
        "department": course.department,
        "courseNumber": course.course_number,
        "name": course.name,
    }


def _post_json(post) -> dict:
    """Serialize Post schema object."""
    return {
        "id": post.id,
        "authorName": post.author_name,
        "body": post.body,
        "createdAt": post.created_at.isoformat() if hasattr(post.created_at, "isoformat") else str(post.created_at),
    }


def _discussion_summary_json(discussion) -> dict:
    """Serialize DiscussionSummary schema object."""
    return {
        "id": discussion.id,
        "title": discussion.title,
        "author": discussion.author,
        "createdAt": discussion.created_at.isoformat() if hasattr(discussion.created_at, "isoformat") else str(discussion.created_at),
        "postCount": discussion.post_count,
    }


def _discussion_group_json(group) -> dict:
    """Serialize DiscussionGroup schema object."""
    return {
        "course": _course_json(group.course),
        "discussions": [_discussion_summary_json(d) for d in group.discussions],
    }


def _discussion_detail_json(discussion) -> dict:
    """Serialize Discussion schema object with embedded posts."""
    return {
        "id": discussion.id,
        "course": _course_json(discussion.course),
        "title": discussion.title,
        "posts": [_post_json(p) for p in discussion.posts],
    }


def create_app(board_app: DiscussionBoardApp) -> Flask:
    """Build the Flask app and register routes."""
    app = Flask(__name__)

    # --- HTML / Template Routes ---

    @app.get("/")
    def index_page():
        return render_template("index.html")

    # --- Health Check Endpoint ---

    @app.get("/health")
    def health():
        try:
            board_app.health()
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"status": "ok"}), 200

    # --- Course Endpoints ---

    @app.get("/courses")
    def list_courses():
        try:
            courses = board_app.list_courses()
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"courses": [_course_json(c) for c in courses]}), 200

    @app.post("/courses")
    def create_course():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _error("BAD_REQUEST", "JSON body required", 400)

        required_fields = ["department", "courseNumber", "name"]
        if not all(field in body for field in required_fields):
            return _error("BAD_REQUEST", "department, courseNumber, and name are required", 400)

        dept = body.get("department")
        course_num = body.get("courseNumber")
        name = body.get("name")

        # Validate constraint lengths per OpenAPI spec
        if not (isinstance(dept, str) and 1 <= len(dept) <= 10):
            return _error("BAD_REQUEST", "department must be 1-10 characters", 400)
        if not (isinstance(course_num, str) and 1 <= len(course_num) <= 10):
            return _error("BAD_REQUEST", "courseNumber must be 1-10 characters", 400)
        if not (isinstance(name, str) and 1 <= len(name) <= 100):
            return _error("BAD_REQUEST", "name must be 1-100 characters", 400)

        try:
            course_id = board_app.create_course(
                department=dept,
                course_number=course_num,
                name=name,
            )
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({"id": course_id}), 201

    # --- Discussion Endpoints ---

    @app.get("/discussions")
    def list_discussions():
        try:
            groups = board_app.list_discussions()
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"groups": [_discussion_group_json(g) for g in groups]}), 200

    @app.post("/discussions")
    def create_discussion():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _error("BAD_REQUEST", "JSON body required", 400)

        required_fields = ["courseId", "title", "authorName", "body"]
        if not all(field in body for field in required_fields):
            return _error("BAD_REQUEST", "courseId, title, authorName, and body are required", 400)

        course_id = body.get("courseId")
        title = body.get("title")
        author_name = body.get("authorName")
        post_body = body.get("body")

        if not isinstance(course_id, int) or course_id < 1:
            return _error("BAD_REQUEST", "courseId must be an integer >= 1", 400)
        if not (isinstance(title, str) and 1 <= len(title) <= 200):
            return _error("BAD_REQUEST", "title must be 1-200 characters", 400)
        if not (isinstance(author_name, str) and 1 <= len(author_name) <= 100):
            return _error("BAD_REQUEST", "authorName must be 1-100 characters", 400)
        if not (isinstance(post_body, str) and len(post_body) >= 1):
            return _error("BAD_REQUEST", "body must be a non-empty string", 400)

        try:
            discussion_id = board_app.create_discussion(
                course_id=course_id,
                title=title,
                author_name=author_name,
                body=post_body,
            )
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except NotFoundError:
            return _error("NOT_FOUND", "Course not found", 404)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({"id": discussion_id}), 201

    @app.get("/discussions/<int:discussion_id>")
    def get_discussion(discussion_id: int):
        try:
            discussion = board_app.get_discussion(discussion_id)
        except NotFoundError:
            return _error("NOT_FOUND", "Discussion not found", 404)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify(_discussion_detail_json(discussion)), 200

    @app.post("/discussions/<int:discussion_id>/posts")
    def create_post(discussion_id: int):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _error("BAD_REQUEST", "JSON body required", 400)

        if "authorName" not in body or "body" not in body:
            return _error("BAD_REQUEST", "authorName and body are required", 400)

        author_name = body.get("authorName")
        post_body = body.get("body")

        if not (isinstance(author_name, str) and 1 <= len(author_name) <= 100):
            return _error("BAD_REQUEST", "authorName must be 1-100 characters", 400)
        if not (isinstance(post_body, str) and len(post_body) >= 1):
            return _error("BAD_REQUEST", "body must be a non-empty string", 400)

        try:
            post = board_app.create_post(
                discussion_id=discussion_id,
                author_name=author_name,
                body=post_body,
            )
        except ValidationError as exc:
            return _error("BAD_REQUEST", str(exc), 400)
        except NotFoundError:
            return _error("NOT_FOUND", "Discussion not found", 404)
        except ServiceUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        # Return full Post object upon creation according to OpenAPI spec
        return jsonify(_post_json(post)), 201

    return app


def launch() -> Flask:
    """Initialize DB connection and application entry point."""
    storage = BoardStorage(...)
    try:
        storage.ping()
    except DatabaseUnavailableError as exc:
        raise RuntimeError(f"Database not reachable: {exc}") from exc

    return create_app(DiscussionBoardApp(storage))


if __name__ == "__main__":
    try:
        app = launch()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    app.run(host="0.0.0.0", port=5000, debug=True)