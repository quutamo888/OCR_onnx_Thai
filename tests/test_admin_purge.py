from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)


def test_purge_all_forbidden_for_user():
    user_token_payload = {"username": "officer1", "role": "user"}
    with patch("server.core.dependencies.verify_token", return_value=user_token_payload):
        res = client.post(
            "/api/admin/cache/purge-all",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 403


def test_purge_all_success_for_admin():
    admin_token_payload = {"username": "admin", "role": "admin"}
    with patch("server.core.dependencies.verify_token", return_value=admin_token_payload), \
         patch("server.routers.admin.purge_all_cached_ocr", return_value=5):
        res = client.post(
            "/api/admin/cache/purge-all",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["purged_count"] == 5


def test_purge_task_success_for_admin():
    admin_token_payload = {"username": "admin", "role": "admin"}
    fake_job = {
        "id": "job123",
        "filename": "test.pdf",
        "s3_input_key": "inputs/job123/test.pdf"
    }
    with patch("server.core.dependencies.verify_token", return_value=admin_token_payload), \
         patch("server.routers.admin.get_job", return_value=fake_job), \
         patch("server.routers.admin.storage.get_object", return_value=b"dummy_bytes"), \
         patch("server.routers.admin.compute_file_hash", return_value="hash123"), \
         patch("server.routers.admin.purge_cached_ocr", return_value=True):
        res = client.post(
            "/api/admin/cache/purge/job123",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["job_id"] == "job123"
        assert data["file_hash"] == "hash123"
        assert data["found"] is True


def test_purge_task_not_found():
    admin_token_payload = {"username": "admin", "role": "admin"}
    with patch("server.core.dependencies.verify_token", return_value=admin_token_payload), \
         patch("server.routers.admin.get_job", return_value=None):
        res = client.post(
            "/api/admin/cache/purge/missing_job",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 404


def test_purge_task_missing_source_file():
    admin_token_payload = {"username": "admin", "role": "admin"}
    fake_job = {
        "id": "job456",
        "filename": "test.pdf",
        "s3_input_key": "inputs/job456/test.pdf"
    }
    with patch("server.core.dependencies.verify_token", return_value=admin_token_payload), \
         patch("server.routers.admin.get_job", return_value=fake_job), \
         patch("server.routers.admin.storage.get_object", return_value=None):
        res = client.post(
            "/api/admin/cache/purge/job456",
            headers={"Authorization": "Bearer fake_token"}
        )
        assert res.status_code == 400
