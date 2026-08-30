from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_readiness():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "JARVIS" in client.get("/").text
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["database"] == "ok"


def test_profile_upsert_and_get():
    with TestClient(app) as client:
        response = client.put(
            "/profile",
            json={"display_name": "Jonghwan", "timezone": "Asia/Seoul"},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Jonghwan"
        assert client.get("/profile").json()["timezone"] == "Asia/Seoul"


def test_direct_memory_upserts_by_normalized_key():
    with TestClient(app) as client:
        first = client.post(
            "/memories",
            json={
                "content": "My name is Jonghwan.",
                "normalized_key": "profile.name",
                "category": "profile",
            },
        )
        second = client.post(
            "/memories",
            json={
                "content": "My preferred name is Tony.",
                "normalized_key": "profile.name",
                "category": "profile",
            },
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["id"] == first.json()["id"]
        assert len(client.get("/memories").json()) == 1
        updated = client.patch(
            f"/memories/{first.json()['id']}",
            json={"importance": 0.8},
        )
        assert updated.status_code == 200
        assert updated.json()["importance"] == 0.8


def test_conversation_history_and_user_ownership(monkeypatch):
    captured_inputs = []

    async def fake_run(*args, **kwargs):
        captured_inputs.append(args[1])
        return SimpleNamespace(final_output="Understood.")

    monkeypatch.setattr("app.main.Runner.run", fake_run)

    with TestClient(app) as client:
        first = client.post(
            "/chat", json={"message": "Remember this context."}
        )
        assert first.status_code == 200
        conversation_id = first.json()["conversation_id"]

        second = client.post(
            "/chat",
            json={
                "conversation_id": conversation_id,
                "message": "Continue.",
            },
        )
        assert second.status_code == 200
        assert [item["role"] for item in captured_inputs[1]] == [
            "system",
            "user",
            "assistant",
            "user",
        ]
        messages = client.get(
            f"/conversations/{conversation_id}/messages"
        )
        assert [item["role"] for item in messages.json()] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
