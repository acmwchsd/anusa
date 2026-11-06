import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from . import websocket_messages
from .json_files import generate_id
from .keyword_matching import KeywordMatch

# A page that sent a camera frame within this window has its camera on.
CAMERA_ACTIVE_WINDOW_SECONDS = 5.0
# Long enough for the countdown (up to 5 s), the photo and the upload.
CAPTURE_TIMEOUT_SECONDS = 15.0


class NoActiveCamera(Exception):
    pass


@dataclass(eq=False)
class ConnectedPage:
    send_message: Callable[[dict], None]
    last_camera_frame_time: float = float("-inf")

    def has_active_camera(self, current_time: float) -> bool:
        return current_time - self.last_camera_frame_time < CAMERA_ACTIVE_WINDOW_SECONDS


@dataclass
class CaptureRequest:
    request_id: str
    page: ConnectedPage
    # Resolves to the saved photo, or to None when no photo arrives in time.
    photo_future: asyncio.Future


class CaptureCoordinator:
    """Runs on the event loop, except report_photo_saved, which any thread may call."""

    def __init__(self) -> None:
        self._connected_pages: set[ConnectedPage] = set()
        self._pending_requests: dict[str, CaptureRequest] = {}
        self._last_voice_trigger_time: float | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None

    def connect_page(self, send_message: Callable[[dict], None]) -> ConnectedPage:
        page = ConnectedPage(send_message)
        self._connected_pages.add(page)
        return page

    def disconnect_page(self, page: ConnectedPage) -> None:
        self._connected_pages.discard(page)

    def try_start_voice_cooldown(self, cooldown_seconds: float) -> bool:
        """True when the keyword may take a photo now, which starts a new cooldown. Shared by all pages."""
        current_time = time.monotonic()
        is_cooling_down = (
            self._last_voice_trigger_time is not None
            and current_time - self._last_voice_trigger_time < cooldown_seconds
        )
        if is_cooling_down:
            return False
        self._last_voice_trigger_time = current_time
        return True

    def request_capture(
        self,
        source: str,
        keyword_match: KeywordMatch | None = None,
        preferred_page: ConnectedPage | None = None,
    ) -> CaptureRequest:
        """Asks a page to take a photo now. A page still busy with an earlier request
        is not asked again: both callers get the same photo."""
        page = self._choose_page(preferred_page)
        if page is None:
            raise NoActiveCamera()
        existing_request = next(
            (request for request in self._pending_requests.values() if request.page is page), None
        )
        if existing_request is not None:
            return existing_request

        self._event_loop = asyncio.get_running_loop()
        capture_request = CaptureRequest(
            request_id=generate_id(), page=page, photo_future=self._event_loop.create_future()
        )
        self._pending_requests[capture_request.request_id] = capture_request
        self._event_loop.call_later(CAPTURE_TIMEOUT_SECONDS, self._resolve_request, capture_request.request_id, None)
        page.send_message(websocket_messages.capture_requested(source, keyword_match, capture_request.request_id))
        return capture_request

    def _choose_page(self, preferred_page: ConnectedPage | None) -> ConnectedPage | None:
        """The preferred page if its camera is on, otherwise the page with the newest camera frame,
        otherwise the preferred page anyway (its camera may still be starting)."""
        current_time = time.monotonic()
        if preferred_page is not None and preferred_page.has_active_camera(current_time):
            return preferred_page
        pages_with_active_camera = [page for page in self._connected_pages if page.has_active_camera(current_time)]
        if pages_with_active_camera:
            return max(pages_with_active_camera, key=lambda page: page.last_camera_frame_time)
        return preferred_page

    def report_photo_saved(self, request_id: str, photo_json: dict) -> None:
        """Thread-safe: the photo upload route calls this from a worker thread."""
        if self._event_loop is not None:
            self._event_loop.call_soon_threadsafe(self._resolve_request, request_id, photo_json)

    def _resolve_request(self, request_id: str, photo_json: dict | None) -> None:
        capture_request = self._pending_requests.pop(request_id, None)
        if capture_request is not None and not capture_request.photo_future.done():
            capture_request.photo_future.set_result(photo_json)
