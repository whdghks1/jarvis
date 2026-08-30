from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app, settings
from app.security.service import authenticate_device


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


def test_device_pairing_and_safe_action_lifecycle():
    with TestClient(app) as client:
        paired = client.post(
            "/device-registration",
            json={"name": "Pixel", "pairing_code": settings.pairing_code},
        )
        assert paired.status_code == 201
        token = paired.json()["access_token"]
        assert authenticate_device(token) is not None

        proposed = client.post(
            "/actions",
            json={
                "action_type": "phone.dial",
                "title": "Call home",
                "payload": {"phone_number": "01000000000"},
            },
        )
        assert proposed.status_code == 201
        assert proposed.json()["status"] == "pending_confirmation"
        action_id = proposed.json()["id"]

        approved = client.post(f"/actions/{action_id}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        completed = client.post(
            f"/actions/{action_id}/result",
            json={"success": True, "detail": "Dialer opened"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"


def test_streaming_chat_persists_final_reply(monkeypatch):
    class FakeStreamingResult:
        final_output = "Hello streamed world."
        run_loop_exception = None
        is_complete = True

        async def stream_events(self):
            for delta in ("Hello ", "streamed ", "world."):
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=SimpleNamespace(
                        type="response.output_text.delta", delta=delta
                    ),
                )

        def cancel(self):
            raise AssertionError("Completed stream should not be cancelled")

    monkeypatch.setattr(
        "app.main.Runner.run_streamed", lambda *args, **kwargs: FakeStreamingResult()
    )

    with TestClient(app) as client:
        with client.stream(
            "POST", "/chat/stream", json={"message": "Stream this"}
        ) as response:
            body = "\n".join(response.iter_lines())
        assert response.status_code == 200
        assert "event: conversation" in body
        assert body.count("event: delta") == 3
        assert "event: done" in body
        conversation_id = int(
            body.split('"conversation_id": ')[1].split("}")[0]
        )
        messages = client.get(f"/conversations/{conversation_id}/messages").json()
        assert messages[-1]["content"] == "Hello streamed world."
