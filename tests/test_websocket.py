import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient
from auth import create_access_token
from api import app
from tasks import run_rag_query


@pytest.fixture
def auth_token():
    return create_access_token({"sub": "ws_test_user"})


class TestWebSocket:
    def test_invalid_token_closes_connection(self):
        with pytest.raises(WebSocketDisconnect):
            with TestClient(app).websocket_connect("/ws/task-0000?token=bad-token") as ws:
                pass

    def test_valid_token_accepts_connection(self, auth_token):
        with TestClient(app).websocket_connect(f"/ws/task-0001?token={auth_token}") as ws:
            pass

    def test_receives_result_when_task_completes(self, auth_token):
        celery_result = run_rag_query.delay("test question")
        task_id = celery_result.id

        with TestClient(app).websocket_connect(f"/ws/{task_id}?token={auth_token}") as ws:
            received_completion = False
            while True:
                data = ws.receive_json()
                if data.get("status") == "completed":
                    assert "result" in data
                    assert data["task_id"] == task_id
                    received_completion = True
                    break
                if data.get("ping"):
                    continue
            assert received_completion

    def test_immediate_result_if_already_completed(self, auth_token):
        celery_result = run_rag_query.delay("quick question")
        task_id = celery_result.id

        with TestClient(app).websocket_connect(f"/ws/{task_id}?token={auth_token}") as ws:
            data = ws.receive_json()
            assert "result" in data or "ping" in data
