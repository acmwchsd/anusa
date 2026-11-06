from fastapi import APIRouter

from .. import websocket_messages
from ..app_state import AppStateDependency
from ..model_downloads import FACE_DETECTOR_MODEL, FACE_RECOGNIZER_MODEL
from ..settings import Settings

router = APIRouter()


@router.get("/api/health")
def get_health(app_state: AppStateDependency) -> dict:
    return {
        "status": "ok",
        "server": "python",
        "models": {"detector": FACE_DETECTOR_MODEL.filename, "recognizer": FACE_RECOGNIZER_MODEL.filename},
        "people": len(app_state.roster.list_people()),
        "samples": app_state.roster.count_reference_photos(),
        "photos": len(app_state.photo_store.list_newest_first()),
        "speech": app_state.speech_status,
    }


@router.get("/api/settings")
def get_settings(app_state: AppStateDependency) -> Settings:
    return app_state.settings


@router.put("/api/settings")
def replace_settings(new_settings: Settings, app_state: AppStateDependency) -> Settings:
    """Replaces every setting. A field that is left out goes back to its default."""
    sanitized_settings = new_settings.sanitized()
    sanitized_settings.save(app_state.config.data_directory)
    app_state.settings = sanitized_settings
    app_state.broadcast(websocket_messages.settings_changed(sanitized_settings))
    return sanitized_settings
