import asyncio
import json
import logging
import time

import numpy as np
from fastapi import APIRouter, WebSocket

from .. import websocket_messages
from ..app_state import AppState, AppStateDependency
from ..face_analysis import DetectedFace, decode_image
from ..face_tracking import FaceTrack, FaceTracker
from ..keyword_matching import find_keyword
from ..voice_activity import SAMPLE_RATE_HZ, UtteranceDetector

logger = logging.getLogger(__name__)
router = APIRouter()

CAMERA_FRAME_MESSAGE = 0x01
MICROPHONE_AUDIO_MESSAGE = 0x02
CAMERA_FRAME_HEADER_LENGTH = 5
MAXIMUM_QUEUED_UTTERANCES = 3
MAXIMUM_EMBEDDINGS_PER_FRAME = 16


@router.websocket("/ws")
async def live_stream(websocket: WebSocket, app_state: AppStateDependency) -> None:
    await websocket.accept()
    await LivePageSession(app_state, websocket).run()


class LivePageSession:
    def __init__(self, app_state: AppState, websocket: WebSocket):
        self.app_state = app_state
        self.websocket = websocket
        self.outbox = app_state.broadcast_hub.subscribe()
        self.connected_page = app_state.capture_coordinator.connect_page(self.queue_message_without_waiting)
        self.face_tracker = FaceTracker()
        self.utterance_detector = UtteranceDetector()
        self.latest_camera_frame: tuple[int, bytes] | None = None
        self.camera_frame_waiting = asyncio.Event()
        self.utterance_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=MAXIMUM_QUEUED_UTTERANCES)

    async def run(self) -> None:
        self.queue_message_without_waiting(websocket_messages.hello(self.app_state.speech_status, self.app_state.settings))
        background_tasks = [
            asyncio.create_task(self.send_queued_messages()),
            asyncio.create_task(self.analyze_camera_frames()),
            asyncio.create_task(self.transcribe_utterances()),
        ]
        try:
            await self.receive_messages()
        finally:
            self.app_state.broadcast_hub.unsubscribe(self.outbox)
            self.app_state.capture_coordinator.disconnect_page(self.connected_page)
            for task in background_tasks:
                task.cancel()
            await asyncio.gather(*background_tasks, return_exceptions=True)

    async def queue_message(self, message: dict) -> None:
        await self.outbox.put(json.dumps(message))

    def queue_message_without_waiting(self, message: dict) -> None:
        try:
            self.outbox.put_nowait(json.dumps(message))
        except asyncio.QueueFull:
            pass

    async def receive_messages(self) -> None:
        while True:
            message = await self.websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes"):
                self.handle_binary_message(message["bytes"])
            elif message.get("text") and '"ping"' in message["text"]:
                self.queue_message_without_waiting(websocket_messages.pong())

    def handle_binary_message(self, data: bytes) -> None:
        message_kind = data[0]
        if message_kind == CAMERA_FRAME_MESSAGE and len(data) > CAMERA_FRAME_HEADER_LENGTH:
            frame_id = int.from_bytes(data[1:CAMERA_FRAME_HEADER_LENGTH], "little")
            self.latest_camera_frame = (frame_id, data[CAMERA_FRAME_HEADER_LENGTH:])
            self.camera_frame_waiting.set()
            self.connected_page.last_camera_frame_time = time.monotonic()
        elif message_kind == MICROPHONE_AUDIO_MESSAGE:
            self.handle_audio_chunk(data[1:])

    def handle_audio_chunk(self, pcm_bytes: bytes) -> None:
        whole_samples_length = len(pcm_bytes) // 2 * 2
        samples = np.frombuffer(pcm_bytes[:whole_samples_length], dtype="<i2")
        was_speaking = self.utterance_detector.is_speaking
        for utterance in self.utterance_detector.add_audio(samples):
            try:
                self.utterance_queue.put_nowait(utterance)
            except asyncio.QueueFull:
                logger.warning("Whisper is falling behind; dropped an utterance")
        if self.utterance_detector.is_speaking != was_speaking:
            self.queue_message_without_waiting(
                websocket_messages.voice_activity_changed(self.utterance_detector.is_speaking)
            )

    async def send_queued_messages(self) -> None:
        while True:
            await self.websocket.send_text(await self.outbox.get())

    async def analyze_camera_frames(self) -> None:
        while True:
            await self.camera_frame_waiting.wait()
            self.camera_frame_waiting.clear()
            frame_id, jpeg_bytes = self.latest_camera_frame
            try:
                frame_result = await asyncio.to_thread(
                    analyze_camera_frame, self.app_state, self.face_tracker, frame_id, jpeg_bytes
                )
                message = websocket_messages.faces_detected(frame_result)
            except Exception as error:  # one bad frame must not stop the video
                logger.warning("frame %d: %s", frame_id, error)
                message = websocket_messages.frame_failed(frame_id, str(error))
            await self.queue_message(message)

    async def transcribe_utterances(self) -> None:
        while True:
            utterance = await self.utterance_queue.get()
            transcriber = self.app_state.transcriber
            if transcriber is None:
                continue
            utterance_seconds = len(utterance) / SAMPLE_RATE_HZ
            await self.queue_message(websocket_messages.transcription_started(utterance_seconds))

            started_at = time.perf_counter()
            try:
                transcript = await transcriber.transcribe(utterance)
            except Exception as error:  # one failed utterance must not stop the voice trigger
                logger.warning("could not transcribe %.1f s of audio: %s", utterance_seconds, error)
                await self.queue_message(websocket_messages.transcription_failed(str(error) or type(error).__name__))
                continue
            elapsed_ms = round((time.perf_counter() - started_at) * 1000)

            settings = self.app_state.settings
            keyword_match = find_keyword(transcript, settings.keywords, settings.keyword_sensitivity)
            await self.queue_message(
                websocket_messages.transcript_ready(transcript, utterance_seconds, elapsed_ms, keyword_match)
            )
            if keyword_match is None:
                continue
            if not self.app_state.capture_coordinator.try_start_voice_cooldown(settings.cooldown_s):
                continue

            logger.info("keyword %r heard as %r: taking a photo", keyword_match.keyword, keyword_match.heard_text)
            self.app_state.capture_coordinator.request_capture(
                "voice", keyword_match, preferred_page=self.connected_page
            )


def analyze_camera_frame(app_state: AppState, face_tracker: FaceTracker, frame_id: int, jpeg_bytes: bytes) -> dict:
    started_at = time.perf_counter()
    image = decode_image(jpeg_bytes)
    decoded_at = time.perf_counter()
    detected_faces = app_state.face_analyzer.detect_faces(image)
    detected_at = time.perf_counter()

    face_tracks = face_tracker.update(detected_faces)
    embedded_face_count = refresh_due_embeddings(app_state, face_tracker, image, detected_faces, face_tracks)
    embedded_at = time.perf_counter()

    match_threshold = app_state.settings.match_threshold
    image_height, image_width = image.shape[:2]
    return {
        "frame": frame_id,
        "width": image_width,
        "height": image_height,
        "faces": [
            describe_live_face(app_state, face, track, match_threshold)
            for face, track in zip(detected_faces, face_tracks)
        ],
        "embedded": embedded_face_count,
        "ms": {
            "decode": seconds_to_milliseconds(decoded_at - started_at),
            "detect": seconds_to_milliseconds(detected_at - decoded_at),
            "embed": seconds_to_milliseconds(embedded_at - detected_at),
            "total": seconds_to_milliseconds(time.perf_counter() - started_at),
        },
    }


def refresh_due_embeddings(
    app_state: AppState,
    face_tracker: FaceTracker,
    image: np.ndarray,
    faces: list[DetectedFace],
    face_tracks: list[FaceTrack],
) -> int:
    """Recomputes the embeddings that are due, new faces first, then the oldest. Returns how many were computed."""
    due_face_indexes = [
        face_index
        for face_index, (face, track) in enumerate(zip(faces, face_tracks))
        if face.is_identifiable and track.needs_new_embedding(face_tracker.frame_number)
    ]
    due_face_indexes.sort(
        key=lambda face_index: (
            face_tracks[face_index].embedding is not None,
            face_tracks[face_index].last_embedded_frame,
        )
    )
    due_face_indexes = due_face_indexes[:MAXIMUM_EMBEDDINGS_PER_FRAME]
    for face_index in due_face_indexes:
        new_embedding = app_state.face_analyzer.compute_embedding(image, faces[face_index])
        face_tracks[face_index].blend_in_embedding(new_embedding, face_tracker.frame_number)
    return len(due_face_indexes)


def describe_live_face(app_state: AppState, face: DetectedFace, track: FaceTrack, match_threshold: float) -> dict:
    closest_match = app_state.roster.find_closest_person(track.embedding) if track.embedding is not None else None
    recognized_match = closest_match if closest_match and closest_match.similarity >= match_threshold else None
    return {
        "track": track.track_id,
        "bbox": [round(value, 1) for value in face.bounding_box],
        "score": round(face.confidence, 3),
        "person_id": recognized_match.person_id if recognized_match else None,
        "name": recognized_match.name if recognized_match else None,
        # The closest person even below the threshold, to help tune the threshold.
        "nearest": closest_match.name if closest_match else None,
        "similarity": round(closest_match.similarity, 3) if closest_match else None,
        "small": not face.is_identifiable,
    }


def seconds_to_milliseconds(seconds: float) -> float:
    return round(seconds * 1000, 1)
