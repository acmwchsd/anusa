import asyncio
import json
from dataclasses import dataclass, field
from typing import Annotated

import numpy as np
from fastapi import Depends
from starlette.requests import HTTPConnection

from .capture_coordinator import CaptureCoordinator
from .class_roster import ClassRoster
from .config import Config
from .face_analysis import DetectedFace, FaceAnalyzer
from .photo_store import PhotoStore
from .settings import Settings
from .transcription import Transcriber, unavailable_speech_status

# Messages waiting for one page. A page that falls this far behind misses broadcasts.
OUTBOX_CAPACITY = 64


class BroadcastHub:
    """Delivers a message to every connected page through each page's outbox queue."""

    def __init__(self) -> None:
        self._outboxes: set[asyncio.Queue] = set()
        self._event_loop: asyncio.AbstractEventLoop | None = None

    def subscribe(self) -> asyncio.Queue:
        self._event_loop = asyncio.get_running_loop()
        outbox: asyncio.Queue = asyncio.Queue(maxsize=OUTBOX_CAPACITY)
        self._outboxes.add(outbox)
        return outbox

    def unsubscribe(self, outbox: asyncio.Queue) -> None:
        self._outboxes.discard(outbox)

    def broadcast(self, message: dict) -> None:
        """Thread-safe: delivery is handed to the event loop that owns the queues."""
        if self._event_loop is None:
            return
        serialized_message = json.dumps(message)
        self._event_loop.call_soon_threadsafe(self._deliver_to_every_outbox, serialized_message)

    def _deliver_to_every_outbox(self, serialized_message: str) -> None:
        for outbox in list(self._outboxes):
            try:
                outbox.put_nowait(serialized_message)
            except asyncio.QueueFull:
                pass


@dataclass
class AppState:
    config: Config
    face_analyzer: FaceAnalyzer
    roster: ClassRoster
    photo_store: PhotoStore
    settings: Settings
    transcriber: Transcriber | None
    speech_status: dict = field(default_factory=unavailable_speech_status)
    broadcast_hub: BroadcastHub = field(default_factory=BroadcastHub)
    capture_coordinator: CaptureCoordinator = field(default_factory=CaptureCoordinator)

    def broadcast(self, message: dict) -> None:
        self.broadcast_hub.broadcast(message)

    def analyze_faces(self, image: np.ndarray) -> list[tuple[DetectedFace, np.ndarray | None]]:
        """Every face in a still image, with an embedding for each face big enough to identify."""
        return [
            (face, self.face_analyzer.compute_embedding(image, face) if face.is_identifiable else None)
            for face in self.face_analyzer.detect_faces(image)
        ]


def get_app_state(connection: HTTPConnection) -> AppState:
    return connection.app.state.app_state


AppStateDependency = Annotated[AppState, Depends(get_app_state)]
