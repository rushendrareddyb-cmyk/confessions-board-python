"""Integration tests against real PostgreSQL and Redis services."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app import cache, db
from app.main import app

client = TestClient(app)


def test_health_checks_real_services():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "postgres": True,
        "redis": True,
    }


def test_post_comment_vote_and_duplicate_vote():
    device_id = f"ci-test-{uuid4().hex}"
    post_id = None

    try:
        # Create a post in PostgreSQL.
        response = client.post(
            "/posts",
            headers={"x-device-id": device_id},
            json={"body": f"CI integration test {uuid4().hex}"},
        )

        assert response.status_code == 201, response.text
        post = response.json()
        post_id = post["id"]

        # Verify the post can be read back from the application.
        response = client.get(f"/posts/{post_id}")
        assert response.status_code == 200, response.text
        assert response.json()["body"] == post["body"]

        # Create a comment stored in PostgreSQL.
        response = client.post(
            f"/posts/{post_id}/comments",
            headers={"x-device-id": device_id},
            json={"body": "Integration test comment"},
        )

        assert response.status_code == 201, response.text
        assert response.json()["post_id"] == post_id

        # Vote once; the application uses PostgreSQL and Redis.
        response = client.post(
            f"/posts/{post_id}/vote",
            headers={"x-device-id": device_id},
            json={"direction": "up"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["score"] == 1

        # The same device must not vote a second time.
        response = client.post(
            f"/posts/{post_id}/vote",
            headers={"x-device-id": device_id},
            json={"direction": "up"},
        )

        assert response.status_code == 409

        # Confirm the updated score persisted in PostgreSQL.
        row = db.one("SELECT score FROM posts WHERE id=%s", (post_id,))
        assert row is not None
        assert row["score"] == 1

    finally:
        # Remove test data and Redis keys even if an assertion fails.
        if post_id is not None:
            db.query(
                "DELETE FROM posts WHERE id=%s",
                (post_id,),
                fetch=False,
            )

            redis_client = cache.client()
            for key in (
                f"votes:{post_id}",
                f"voted:{post_id}:*",
                f"reported:{post_id}:*",
            ):
                for found_key in redis_client.scan_iter(key):
                    redis_client.delete(found_key)

                # Rate-limit keys are scoped to a daily salted device bucket.
        # They expire automatically; leave them alone during cleanup.
