
"""Flask application for the classroom discussion board."""

import sys
from collections import defaultdict
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

from discussion_board.db import (
    CourseNotFoundError,
    DatabaseUnavailableError,
    DiscussionNotFoundError,
    DiscussionStorage,
)


def _error(code: str, message: str, status: int):
    """Format a standard API error response."""
    return jsonify({"error": {"code": code, "message": message}}), status


def _format_datetime(value) -> str | None:
    """Convert a database datetime or date to an ISO-formatted string."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _course_json(course: dict) -> dict:
    """Serialize a course database record."""
    return {
        "id": course["course_id"],
        "department": course["department"],
        "courseNumber": course["course_number"],
        "name": course.get("course_name", course["name"])
        if "course_name" in course
        else course["name"],
    }


def _post_json(post: dict) -> dict:
    """Serialize a post database record."""
    return {
        "id": post["post_id"],
        "authorName": post["author_name"],
        "body": post["body"],
        "createdAt": _format_datetime(post["created_at"]),
    }


def _discussion_summary_json(discussion: dict) -> dict:
    """Serialize a discussion summary database record."""
    return {
        "id": discussion["discussion_id"],
        "title": discussion["title"],
        "prompt": discussion["prompt"],
        "createdAt": _format_datetime(discussion["created_at"]),
        "postCount": discussion["post_count"],
    }


def _discussion_group_json(group: dict) -> dict:
    """Serialize a course and its discussions."""
    return {
        "course": group["course"],
        "discussions": group["discussions"],
    }


def _discussion_detail_json(discussion: dict) -> dict:
    """Serialize a discussion record with its embedded posts."""
    course = {
        "course_id": discussion["course_id"],
        "department": discussion["department"],
        "course_number": discussion["course_number"],
        "course_name": discussion["course_name"],
    }

    return {
        "id": discussion["discussion_id"],
        "course": _course_json(course),
        "title": discussion["title"],
        "prompt": discussion["prompt"],
        "createdAt": _format_datetime(discussion["created_at"]),
        "posts": [_post_json(post) for post in discussion["posts"]],
    }


def create_app(storage: DiscussionStorage) -> Flask:
    """Build the Flask application and register its routes."""
    app = Flask(__name__)

    # --- HTML / Template Routes ---

    @app.get("/")
    def index_page():
        return render_template("index.html")

    # --- Health Check Endpoint ---

    @app.get("/health")
    def health():
        try:
            storage.ping()
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({"status": "ok"}), 200

    # --- Course Endpoints ---

    @app.get("/courses")
    def list_courses():
        try:
            courses = storage.list_courses()
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({
            "courses": [_course_json(course) for course in courses]
        }), 200

    @app.post("/courses")
    def create_course():
        body = request.get_json(silent=True)

        if not isinstance(body, dict):
            return _error("BAD_REQUEST", "JSON body required", 400)

        required_fields = ["department", "courseNumber", "name"]
        if not all(field in body for field in required_fields):
            return _error(
                "BAD_REQUEST",
                "department, courseNumber, and name are required",
                400,
            )

        department = body.get("department")
        course_number = body.get("courseNumber")
        name = body.get("name")

        if not (
            isinstance(department, str)
            and 1 <= len(department) <= 10
        ):
            return _error(
                "BAD_REQUEST",
                "department must be 1-10 characters",
                400,
            )

        if not (
            isinstance(course_number, str)
            and 1 <= len(course_number) <= 10
        ):
            return _error(
                "BAD_REQUEST",
                "courseNumber must be 1-10 characters",
                400,
            )

        if not isinstance(name, str) or not 1 <= len(name) <= 100:
            return _error(
                "BAD_REQUEST",
                "name must be 1-100 characters",
                400,
            )

        try:
            course_id = storage.add_course(
                department=department,
                course_number=course_number,
                name=name,
            )
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({"id": course_id}), 201

    # --- Discussion Endpoints ---

    @app.get("/discussions")
    def list_discussions():
        try:
            discussions = storage.list_discussions()
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        # Group the flat database results by course.
        groups = {}

        for discussion in discussions:
            course_id = discussion["course_id"]

            if course_id not in groups:
                course = {
                    "course_id": course_id,
                    "department": discussion["department"],
                    "course_number": discussion["course_number"],
                    "course_name": discussion["course_name"],
                }

                groups[course_id] = {
                    "course": _course_json(course),
                    "discussions": [],
                }

            groups[course_id]["discussions"].append(
                _discussion_summary_json(discussion)
            )

        return jsonify({
            "groups": [
                _discussion_group_json(group)
                for group in groups.values()
            ]
        }), 200

    @app.post("/discussions")
    def create_discussion():
        body = request.get_json(silent=True)

        if not isinstance(body, dict):
            return _error("BAD_REQUEST", "JSON body required", 400)

        required_fields = ["courseId", "title", "prompt"]
        if not all(field in body for field in required_fields):
            return _error(
                "BAD_REQUEST",
                "courseId, title, and prompt are required",
                400,
            )

        course_id = body.get("courseId")
        title = body.get("title")
        prompt = body.get("prompt")

        if (
            not isinstance(course_id, int)
            or isinstance(course_id, bool)
            or course_id < 1
        ):
            return _error(
                "BAD_REQUEST",
                "courseId must be an integer >= 1",
                400,
            )

        if not isinstance(title, str) or not 1 <= len(title) <= 200:
            return _error(
                "BAD_REQUEST",
                "title must be 1-200 characters",
                400,
            )

        if not isinstance(prompt, str) or len(prompt) < 1:
            return _error(
                "BAD_REQUEST",
                "prompt must be a non-empty string",
                400,
            )

        try:
            discussion_id = storage.add_discussion(
                course_id=course_id,
                title=title,
                prompt=prompt,
            )
        except CourseNotFoundError:
            return _error("NOT_FOUND", "Course not found", 404)
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify({"id": discussion_id}), 201

    @app.get("/discussions/<int:discussion_id>")
    def get_discussion(discussion_id: int):
        try:
            discussion = storage.get_discussion(discussion_id)
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        if discussion is None:
            return _error("NOT_FOUND", "Discussion not found", 404)

        return jsonify(_discussion_detail_json(discussion)), 200

    @app.post("/discussions/<int:discussion_id>/posts")
    def create_post(discussion_id: int):
        body = request.get_json(silent=True)

        if not isinstance(body, dict):
            return _error("BAD_REQUEST", "JSON body required", 400)

        if "authorName" not in body or "body" not in body:
            return _error(
                "BAD_REQUEST",
                "authorName and body are required",
                400,
            )

        author_name = body.get("authorName")
        post_body = body.get("body")

        if (
            not isinstance(author_name, str)
            or not 1 <= len(author_name) <= 100
        ):
            return _error(
                "BAD_REQUEST",
                "authorName must be 1-100 characters",
                400,
            )

        if not isinstance(post_body, str) or len(post_body) < 1:
            return _error(
                "BAD_REQUEST",
                "body must be a non-empty string",
                400,
            )

        try:
            post_id = storage.add_post(
                discussion_id=discussion_id,
                author_name=author_name,
                body=post_body,
            )

            # add_post returns only the new ID, so retrieve the
            # inserted record to return the complete Post response.
            posts = storage.list_posts(discussion_id)
            post = next(
                (item for item in posts if item["post_id"] == post_id),
                None,
            )

            if post is None:
                return jsonify({
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Created post could not be retrieved",
                    }
                }), 500

        except DiscussionNotFoundError:
            return _error("NOT_FOUND", "Discussion not found", 404)
        except DatabaseUnavailableError:
            return jsonify({"status": "unavailable"}), 503

        return jsonify(_post_json(post)), 201

    return app


def launch() -> Flask:
    """Initialize the database connection and Flask application."""
    storage = DiscussionStorage()

    try:
        storage.ping()
    except DatabaseUnavailableError as exc:
        raise RuntimeError(
            f"Database not reachable: {exc}"
        ) from exc

    return create_app(storage)


app = launch()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)