from .. import websocket_messages
from ..app_state import AppState
from ..errors import ApiError

MAXIMUM_NAME_LENGTH = 80
CACHE_FOREVER_HEADERS = {"Cache-Control": "private, max-age=31536000, immutable"}


def validate_name(name: str) -> str:
    trimmed_name = name.strip()
    if not trimmed_name or len(trimmed_name) > MAXIMUM_NAME_LENGTH:
        raise ApiError.bad_request(f"name must be 1-{MAXIMUM_NAME_LENGTH} characters")
    return trimmed_name


def notify_roster_changed(app_state: AppState) -> None:
    app_state.broadcast(websocket_messages.roster_changed(app_state.roster.version))
