"""The whole server through its HTTP API and the live WebSocket, the way the web app uses it.
Each test gets an empty data directory of its own."""

import json
import struct
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import capture_coordinator
from app.config import Config
from app.main import create_app
from app.voice_activity import SAMPLE_RATE_HZ

from .conftest import MODELS_DIRECTORY, encode_test_jpeg, face_close_up, place_side_by_side, requires_face_models

pytestmark = requires_face_models

EMPTY_ROOM_IMAGE = np.full((240, 320, 3), 90, np.uint8)


@pytest.fixture
def client(tmp_path):
    config = Config(
        host="127.0.0.1",
        port=0,
        models_directory=MODELS_DIRECTORY,
        data_directory=tmp_path,
        web_build_directory=None,
        speech_api_url=None,
        opencv_threads=2,
        speech_engine="off",
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client


def enroll_person(client, name: str, which_person: str) -> dict:
    person = client.post("/api/people", json={"name": name}).json()
    close_ups = [face_close_up(which_person, zoom) for zoom in (3.5, 4.0)]
    close_ups.append(face_close_up(which_person, 4.5, mirror=True))
    files = [
        ("image", (f"{which_person}-{index}.jpg", encode_test_jpeg(image), "image/jpeg"))
        for index, image in enumerate(close_ups)
    ]
    response = client.post(f"/api/people/{person['id']}/samples", files=files, data={"source": "upload"}).json()
    assert response["rejected"] == []
    return response["person"]


def camera_frame_message(frame_id: int, image: np.ndarray) -> bytes:
    return bytes([0x01]) + struct.pack("<I", frame_id) + encode_test_jpeg(image)


def receive_until(websocket, message_type: str) -> list[dict]:
    """Every message up to and including the first one of `message_type`."""
    messages = [websocket.receive_json()]
    while messages[-1]["type"] != message_type:
        messages.append(websocket.receive_json())
    return messages


def say_a_word(websocket, until_message_type: str) -> list[dict]:
    """Streams 1 s of quiet, 0.8 s of a loud hum and 1 s of quiet, 100 ms at a time like the browser."""
    times = np.arange(SAMPLE_RATE_HZ) / SAMPLE_RATE_HZ
    spoken_word = (8000 * np.sin(2 * np.pi * 220 * times[: SAMPLE_RATE_HZ * 8 // 10])).astype("<i2")
    quiet = np.zeros(SAMPLE_RATE_HZ, "<i2")
    audio_bytes = np.concatenate([quiet, spoken_word, quiet]).tobytes()
    chunk_length = 3200
    for chunk_start in range(0, len(audio_bytes), chunk_length):
        websocket.send_bytes(bytes([0x02]) + audio_bytes[chunk_start : chunk_start + chunk_length])
    return receive_until(websocket, until_message_type)


def turn_camera_on(websocket) -> None:
    """Sends a camera frame like the Live page does, and waits for its answer."""
    websocket.send_bytes(camera_frame_message(1, EMPTY_ROOM_IMAGE))
    receive_until(websocket, "faces")


class FakeTranscriber:
    """Stands in for Whisper and hears the same words every time."""

    location = "fake"

    async def transcribe(self, samples):
        return "Okay everyone, Techpreneur."

    async def close(self):
        pass


def test_health_and_settings(client, tmp_path):
    health = client.get("/api/health").json()
    assert (health["status"], health["server"], health["people"]) == ("ok", "python", 0)

    saved_settings = client.put("/api/settings", json={"match_threshold": 5, "keywords": [" cheese ", ""]}).json()
    # clamped, trimmed, and the fields left out are back to their defaults
    assert saved_settings == {
        "match_threshold": 0.95,
        "keywords": ["cheese"],
        "keyword_sensitivity": 0.75,
        "cooldown_s": 3.0,
    }
    assert json.loads((tmp_path / "settings.json").read_text()) == saved_settings


def test_the_class_roster(client):
    response = client.post("/api/people", json={"name": " Alice "})
    assert response.status_code == 201
    assert response.json()["name"] == "Alice"
    assert client.post("/api/people", json={"name": "alice"}).status_code == 409
    assert client.post("/api/people", json={"name": "  "}).json() == {"error": "name must be 1-80 characters"}
    assert client.post("/api/people", json={}).status_code == 422

    person_id = response.json()["id"]
    assert client.patch(f"/api/people/{person_id}", json={"name": "Alicia"}).json()["name"] == "Alicia"
    assert client.delete(f"/api/people/{person_id}").status_code == 204
    assert client.get(f"/api/people/{person_id}").json() == {"error": "person not found"}
    assert client.get("/api/people/not-a-uuid").status_code == 422


def test_enrolling_reference_photos(client):
    person = client.post("/api/people", json={"name": "Student A"}).json()
    files = [
        ("image", ("face.jpg", encode_test_jpeg(face_close_up("left")), "image/jpeg")),
        ("image", ("notes.txt", b"not an image", "text/plain")),
        ("image", ("far.jpg", encode_test_jpeg(face_close_up("left", zoom=0.8)), "image/jpeg")),
    ]
    response = client.post(f"/api/people/{person['id']}/samples", files=files).json()
    assert [added["file"] for added in response["added"]] == ["face.jpg"]
    assert [rejected["file"] for rejected in response["rejected"]] == ["notes.txt", "far.jpg"]
    assert "px wide" in response["rejected"][1]["error"]

    reference_photo = response["added"][0]["sample"]
    assert set(reference_photo) == {"id", "created_at", "source"}
    thumbnail = client.get(f"/api/people/{person['id']}/samples/{reference_photo['id']}/image")
    assert thumbnail.headers["content-type"] == "image/jpeg"


def test_photos_are_named_and_can_teach_new_students(client, tmp_path):
    student_a = enroll_person(client, "Student A", "left")

    class_photo = place_side_by_side(face_close_up("left", 3.8), face_close_up("right", 3.8))
    response = client.post(
        "/api/photos",
        files={"photo": ("photo.jpg", encode_test_jpeg(class_photo), "image/jpeg")},
        data={"trigger": "key"},
    )
    assert response.status_code == 201
    photo = response.json()
    assert photo["people"] == ["Student A"]
    left_face, right_face = photo["faces"]
    assert (left_face["name"], left_face["person_id"], right_face["name"]) == ("Student A", student_a["id"], None)

    labeled_photo = client.put(
        f"/api/photos/{photo['id']}/faces/{right_face['index']}", json={"name": "Student B"}
    ).json()
    assert labeled_photo["people"] == ["Student A", "Student B"]
    student_b = next(person for person in client.get("/api/people").json() if person["name"] == "Student B")
    assert student_b["samples"][0]["source"] == f"photo:{photo['id']}"

    # clearing the label leaves the match, because Student B is enrolled now
    cleared_photo = client.put(f"/api/photos/{photo['id']}/faces/{right_face['index']}", json={}).json()
    assert cleared_photo["faces"][1]["assigned"] is False
    assert cleared_photo["faces"][1]["name"] == "Student B"

    saved_metadata = json.loads((tmp_path / "photos" / f"{photo['id']}.json").read_text())
    assert set(saved_metadata) == {"id", "taken_at", "width", "height", "bytes", "trigger", "heard", "faces"}
    assert len(saved_metadata["faces"][0]["embedding"]) == 128
    saved_roster = json.loads((tmp_path / "gallery.json").read_text())
    assert len(saved_roster["people"][0]["samples"][0]["embedding"]) == 128

    assert client.delete(f"/api/photos/{photo['id']}").status_code == 204
    assert client.get("/api/photos").json() == []


def test_photo_upload_errors(client):
    assert client.post("/api/photos", data={"trigger": "key"}).json() == {"error": "missing `photo` file"}
    response = client.post("/api/photos", files={"photo": ("photo.jpg", b"nope", "image/jpeg")})
    assert response.status_code == 415


def test_the_live_stream(client):
    enroll_person(client, "Student A", "left")
    with client.websocket_connect("/ws") as websocket:
        hello = websocket.receive_json()
        assert hello["type"] == "hello"
        assert hello["settings"]["keywords"] == ["techpreneure"]

        websocket.send_bytes(camera_frame_message(7, face_close_up("left", 3.0)))
        faces_message = websocket.receive_json()
        assert faces_message["type"] == "faces"
        assert (faces_message["frame"], faces_message["embedded"]) == (7, 1)
        (live_face,) = faces_message["faces"]
        assert live_face["name"] == "Student A"
        assert live_face["small"] is False
        assert set(faces_message["ms"]) == {"decode", "detect", "embed", "total"}

        # the next frame reuses the track, so there is nothing to embed
        websocket.send_bytes(camera_frame_message(8, face_close_up("left", 3.0)))
        next_faces_message = websocket.receive_json()
        assert next_faces_message["faces"][0]["track"] == live_face["track"]
        assert next_faces_message["embedded"] == 0

        websocket.send_bytes(bytes([0x01]) + struct.pack("<I", 9) + b"not a jpeg")
        assert websocket.receive_json() == {
            "type": "error",
            "frame": 9,
            "message": "not a readable image (JPEG, PNG or WebP)",
        }

        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}

        # news reaches every open page
        client.put("/api/settings", json={"keywords": ["cheese"]})
        assert websocket.receive_json()["type"] == "settings"


def test_the_voice_trigger(client):
    client.app.state.app_state.transcriber = FakeTranscriber()
    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()  # hello
        messages = say_a_word(websocket, until_message_type="trigger")
        assert [message["type"] for message in messages] == ["vad", "vad", "transcribing", "transcript", "trigger"]
        assert [message["speaking"] for message in messages[:2]] == [True, False]
        transcript_message, trigger_message = messages[3], messages[4]
        assert transcript_message["hit"]["heard"] == "techpreneur"
        assert trigger_message == {
            "type": "trigger",
            "source": "voice",
            "hit": transcript_message["hit"],
            "request_id": trigger_message["request_id"],
        }

        # said again within the cooldown: transcribed, but no second photo
        messages_said_again = say_a_word(websocket, until_message_type="transcript")
        assert messages_said_again[-1]["hit"] is not None
        websocket.send_text(json.dumps({"type": "ping"}))
        assert websocket.receive_json() == {"type": "pong"}


def test_the_voice_trigger_uses_the_page_whose_camera_is_on(client):
    client.app.state.app_state.transcriber = FakeTranscriber()
    with client.websocket_connect("/ws") as camera_page, client.websocket_connect("/ws") as microphone_page:
        camera_page.receive_json()
        microphone_page.receive_json()
        turn_camera_on(camera_page)
        assert say_a_word(microphone_page, until_message_type="transcript")[-1]["hit"] is not None
        assert receive_until(camera_page, "trigger")[-1]["source"] == "voice"
        microphone_page.send_text(json.dumps({"type": "ping"}))
        assert microphone_page.receive_json() == {"type": "pong"}


def test_capture_needs_a_page_with_its_camera_on(client):
    assert client.post("/api/capture").status_code == 409
    with client.websocket_connect("/ws") as page_without_camera:
        page_without_camera.receive_json()
        response = client.post("/api/capture")
    assert response.status_code == 409
    assert response.json() == {"error": "no camera is on: open the Live page and allow the camera"}


def test_capture_returns_the_photo_the_live_page_sends(client):
    with client.websocket_connect("/ws") as live_page, ThreadPoolExecutor(max_workers=1) as background:
        live_page.receive_json()
        turn_camera_on(live_page)
        # the capture request waits for the photo, so it runs in the background while this test plays the Live page
        pending_capture = background.submit(client.post, "/api/capture")
        trigger_message = receive_until(live_page, "trigger")[-1]
        assert (trigger_message["source"], trigger_message["hit"]) == ("api", None)

        upload_response = client.post(
            "/api/photos",
            files={"photo": ("photo.jpg", encode_test_jpeg(EMPTY_ROOM_IMAGE), "image/jpeg")},
            data={"trigger": "api", "request_id": trigger_message["request_id"]},
        )
        assert upload_response.status_code == 201
        capture_response = pending_capture.result(timeout=10)

    assert capture_response.status_code == 201
    assert capture_response.json() == upload_response.json()
    assert capture_response.json()["trigger"] == "api"


def test_capture_gives_up_when_no_photo_arrives(client, monkeypatch):
    monkeypatch.setattr(capture_coordinator, "CAPTURE_TIMEOUT_SECONDS", 0.2)
    with client.websocket_connect("/ws") as live_page:
        live_page.receive_json()
        turn_camera_on(live_page)
        response = client.post("/api/capture")
    assert response.status_code == 504
    assert response.json() == {"error": "the Live page sent no photo within 0.2 s"}
