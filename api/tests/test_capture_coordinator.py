import asyncio
import threading
import time

import pytest

from app import capture_coordinator
from app.capture_coordinator import CaptureCoordinator, NoActiveCamera


class FakePage:
    """Stands in for an open page and keeps every message the coordinator sends it."""

    def __init__(self, coordinator: CaptureCoordinator, seconds_since_last_frame: float | None):
        self.received_messages: list[dict] = []
        self.connected_page = coordinator.connect_page(self.received_messages.append)
        if seconds_since_last_frame is not None:
            self.connected_page.last_camera_frame_time = time.monotonic() - seconds_since_last_frame


def test_chooses_which_page_takes_the_photo():
    async def scenario():
        coordinator = CaptureCoordinator()
        photos_page = FakePage(coordinator, seconds_since_last_frame=None)
        camera_turned_off_page = FakePage(coordinator, seconds_since_last_frame=60)
        live_page = FakePage(coordinator, seconds_since_last_frame=0.5)
        newest_camera_page = FakePage(coordinator, seconds_since_last_frame=0.1)

        voice_request = coordinator.request_capture("voice", preferred_page=live_page.connected_page)
        assert voice_request.page is live_page.connected_page

        api_request = coordinator.request_capture("api")
        assert api_request.page is newest_camera_page.connected_page
        assert coordinator.request_capture("api") is api_request
        assert [message["type"] for message in newest_camera_page.received_messages] == ["trigger"]
        assert photos_page.received_messages == camera_turned_off_page.received_messages == []

        coordinator = CaptureCoordinator()
        starting_page = FakePage(coordinator, seconds_since_last_frame=None)
        fallback_request = coordinator.request_capture("voice", preferred_page=starting_page.connected_page)
        assert fallback_request.page is starting_page.connected_page
        with pytest.raises(NoActiveCamera):
            coordinator.request_capture("api")

    asyncio.run(scenario())


def test_the_saved_photo_reaches_whoever_asked():
    async def scenario():
        coordinator = CaptureCoordinator()
        page = FakePage(coordinator, seconds_since_last_frame=0)
        capture_request = coordinator.request_capture("api")
        assert page.received_messages == [
            {"type": "trigger", "source": "api", "hit": None, "request_id": capture_request.request_id}
        ]

        upload_thread = threading.Thread(
            target=coordinator.report_photo_saved, args=(capture_request.request_id, {"id": "photo-1"})
        )
        upload_thread.start()
        assert await asyncio.wait_for(capture_request.photo_future, 2) == {"id": "photo-1"}
        assert coordinator.request_capture("api") is not capture_request

    asyncio.run(scenario())


def test_resolves_to_none_when_no_photo_arrives_in_time(monkeypatch):
    monkeypatch.setattr(capture_coordinator, "CAPTURE_TIMEOUT_SECONDS", 0.05)

    async def scenario():
        coordinator = CaptureCoordinator()
        FakePage(coordinator, seconds_since_last_frame=0)
        capture_request = coordinator.request_capture("api")
        assert await asyncio.wait_for(capture_request.photo_future, 2) is None
        coordinator.report_photo_saved(capture_request.request_id, {"id": "too-late"})
        await asyncio.sleep(0.01)

    asyncio.run(scenario())


def test_one_voice_cooldown_for_every_page():
    coordinator = CaptureCoordinator()
    assert coordinator.try_start_voice_cooldown(3.0)
    assert not coordinator.try_start_voice_cooldown(3.0)
    assert coordinator.try_start_voice_cooldown(0.0)
