from .keyword_matching import KeywordMatch
from .settings import Settings


def hello(speech_status: dict, settings: Settings) -> dict:
    return {"type": "hello", "speech": speech_status, "settings": settings.model_dump()}


def faces_detected(frame_result: dict) -> dict:
    return {"type": "faces", **frame_result}


def frame_failed(frame_id: int, error_message: str) -> dict:
    return {"type": "error", "frame": frame_id, "message": error_message}


def voice_activity_changed(is_speaking: bool) -> dict:
    return {"type": "vad", "speaking": is_speaking}


def transcription_started(utterance_seconds: float) -> dict:
    return {"type": "transcribing", "seconds": utterance_seconds}


def transcript_ready(
    transcript: str, utterance_seconds: float, elapsed_ms: int, keyword_match: KeywordMatch | None
) -> dict:
    return {
        "type": "transcript",
        "text": transcript,
        "seconds": utterance_seconds,
        "elapsed_ms": elapsed_ms,
        "hit": keyword_match.to_json() if keyword_match else None,
    }


def transcription_failed(error_message: str) -> dict:
    return {"type": "speech_error", "message": error_message}


def capture_requested(source: str, keyword_match: KeywordMatch | None, request_id: str) -> dict:
    """Asks a Live page to take a photo now and post it with request_id. Source is "voice" or "api"."""
    return {
        "type": "trigger",
        "source": source,
        "hit": keyword_match.to_json() if keyword_match else None,
        "request_id": request_id,
    }


def pong() -> dict:
    return {"type": "pong"}


def speech_status_changed(speech_status: dict) -> dict:
    return {"type": "speech_status", "speech": speech_status}


def settings_changed(settings: Settings) -> dict:
    return {"type": "settings", "settings": settings.model_dump()}


def photo_taken(photo_json: dict) -> dict:
    return {"type": "photo", "photo": photo_json}


def photo_deleted(photo_id: str) -> dict:
    return {"type": "photo_deleted", "id": photo_id}


def roster_changed(roster_version: int) -> dict:
    return {"type": "gallery", "version": roster_version}
