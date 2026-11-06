import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import capture_coordinator, websocket_messages
from ..app_state import AppState, AppStateDependency
from ..errors import ApiError
from ..face_analysis import DetectedFace, create_face_thumbnail, decode_image
from ..json_files import current_utc_timestamp, generate_id
from ..photo_store import Photo, PhotoFace
from .route_helpers import CACHE_FOREVER_HEADERS, notify_roster_changed, validate_name

logger = logging.getLogger(__name__)
router = APIRouter()

MAXIMUM_TRIGGER_LENGTH = 32


def photo_to_api_json(app_state: AppState, photo: Photo) -> dict:
    return photo.to_api_json(app_state.roster, app_state.settings.match_threshold)


@router.get("/api/photos")
def list_photos(app_state: AppStateDependency) -> list[dict]:
    return [photo_to_api_json(app_state, photo) for photo in app_state.photo_store.list_newest_first()]


@router.get("/api/photos/{photo_id}")
def get_photo(photo_id: UUID, app_state: AppStateDependency) -> dict:
    photo = app_state.photo_store.get_photo(str(photo_id))
    if photo is None:
        raise ApiError.not_found("photo")
    return photo_to_api_json(app_state, photo)


@router.post("/api/photos", status_code=201)
def save_photo(
    app_state: AppStateDependency,
    photo: Annotated[UploadFile | None, File()] = None,
    trigger: Annotated[str, Form()] = "button",
    heard_text: Annotated[str, Form(alias="heard")] = "",
    request_id: Annotated[str, Form()] = "",
) -> dict:
    """Saves a full-resolution photo from the browser. request_id is set when the server asked for the photo."""
    if photo is None:
        raise ApiError.bad_request("missing `photo` file")
    jpeg_bytes = photo.file.read()
    try:
        image = decode_image(jpeg_bytes)
    except ValueError as error:
        raise ApiError(415, str(error))

    image_height, image_width = image.shape[:2]
    saved_photo = Photo(
        photo_id=generate_id(),
        taken_at=current_utc_timestamp(),
        width=image_width,
        height=image_height,
        file_size_bytes=len(jpeg_bytes),
        trigger=trigger[:MAXIMUM_TRIGGER_LENGTH],
        heard_text=heard_text or None,
        faces=[PhotoFace.from_detection(face, embedding) for face, embedding in app_state.analyze_faces(image)],
    )
    app_state.photo_store.add_photo(saved_photo, jpeg_bytes)

    photo_json = photo_to_api_json(app_state, saved_photo)
    logger.info("photo %s (%dx%d): %s", saved_photo.photo_id, image_width, image_height, photo_json["people"])
    app_state.broadcast(websocket_messages.photo_taken(photo_json))
    if request_id:
        app_state.capture_coordinator.report_photo_saved(request_id, photo_json)
    return photo_json


@router.post("/api/capture", status_code=201)
async def capture_photo(app_state: AppStateDependency) -> dict:
    """Takes a photo now with the camera of an open Live page and returns it, just like saying the keyword."""
    try:
        capture_request = app_state.capture_coordinator.request_capture("api")
    except capture_coordinator.NoActiveCamera:
        raise ApiError.conflict("no camera is on: open the Live page and allow the camera")
    # Shielded, so a caller that disconnects does not cancel the photo for others waiting on the same request.
    photo_json = await asyncio.shield(capture_request.photo_future)
    if photo_json is None:
        timeout_seconds = capture_coordinator.CAPTURE_TIMEOUT_SECONDS
        raise ApiError(504, f"the Live page sent no photo within {timeout_seconds:g} s")
    return photo_json


@router.get("/api/photos/{photo_id}/image")
def get_photo_image(photo_id: UUID, app_state: AppStateDependency) -> FileResponse:
    image_path = app_state.photo_store.image_path(str(photo_id))
    if not image_path.exists():
        raise ApiError.not_found("photo")
    return FileResponse(image_path, media_type="image/jpeg", headers=CACHE_FOREVER_HEADERS)


@router.delete("/api/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: UUID, app_state: AppStateDependency) -> Response:
    if not app_state.photo_store.remove_photo(str(photo_id)):
        raise ApiError.not_found("photo")
    app_state.broadcast(websocket_messages.photo_deleted(str(photo_id)))
    return Response(status_code=204)


class FaceLabelRequest(BaseModel):
    # An enrolled person...
    person_id: UUID | None = None
    # ...or the name of a new person to enroll from this face.
    name: str | None = None
    # Also keep this face as a reference photo.
    learn: bool = True

    def names_someone(self) -> bool:
        """Neither a person nor a name means: clear the label."""
        return self.person_id is not None or self.name is not None


@router.put("/api/photos/{photo_id}/faces/{face_index}")
def label_face(
    photo_id: UUID, face_index: int, label_request: FaceLabelRequest, app_state: AppStateDependency
) -> dict:
    """Labels a face in a photo and, by default, learns it as a reference photo.
    The quickest way to enroll a whole class is from one group photo."""
    photo = app_state.photo_store.get_photo(str(photo_id))
    if photo is None or not 0 <= face_index < len(photo.faces):
        raise ApiError.not_found("face")
    face = photo.faces[face_index].to_detection()

    if label_request.names_someone() and label_request.learn and not face.is_identifiable:
        raise ApiError.bad_request("this face is too small to learn from")

    person_id = resolve_labeled_person(app_state, label_request)
    if person_id and label_request.learn:
        learn_face_from_photo(app_state, photo.photo_id, face, person_id)

    updated_photo = app_state.photo_store.assign_face(photo.photo_id, face_index, person_id)
    if updated_photo is None:
        raise ApiError.not_found("face")
    notify_roster_changed(app_state)
    return photo_to_api_json(app_state, updated_photo)


def resolve_labeled_person(app_state: AppState, label_request: FaceLabelRequest) -> str | None:
    """The labeled person's id, enrolling a new person when the label is a new name."""
    if label_request.person_id is not None:
        person = app_state.roster.get_person(str(label_request.person_id))
        if person is None:
            raise ApiError.not_found("person")
        return person["id"]
    if label_request.name is not None:
        name = validate_name(label_request.name)
        return app_state.roster.find_person_id_by_name(name) or app_state.roster.add_person(name)["id"]
    return None


def learn_face_from_photo(app_state: AppState, photo_id: str, face: DetectedFace, person_id: str) -> None:
    image = decode_image(app_state.photo_store.image_path(photo_id).read_bytes())
    embedding = app_state.face_analyzer.compute_embedding(image, face)
    thumbnail_jpeg = create_face_thumbnail(image, face)
    app_state.roster.add_reference_photo(person_id, embedding, thumbnail_jpeg, f"photo:{photo_id}")
