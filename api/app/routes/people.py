from typing import Annotated
from uuid import UUID

import cv2
from fastapi import APIRouter, File, Form, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..app_state import AppState, AppStateDependency
from ..errors import ApiError
from ..face_analysis import create_face_thumbnail, decode_image
from .route_helpers import CACHE_FOREVER_HEADERS, notify_roster_changed, validate_name

router = APIRouter()

# Reference photos with a narrower face than this (in pixels) make poor references.
MINIMUM_REFERENCE_FACE_WIDTH = 40.0
# Warn when a new reference photo matches someone else this far above the match threshold.
LOOKALIKE_WARNING_MARGIN = 0.05
ALLOWED_REFERENCE_PHOTO_SOURCES = ("upload", "camera")


class NameRequest(BaseModel):
    name: str


@router.get("/api/people")
def list_people(app_state: AppStateDependency) -> list[dict]:
    return app_state.roster.list_people()


@router.post("/api/people", status_code=201)
def create_person(name_request: NameRequest, app_state: AppStateDependency) -> dict:
    name = validate_name(name_request.name)
    if app_state.roster.find_person_id_by_name(name):
        raise ApiError.conflict(f"{name} is already enrolled")
    person = app_state.roster.add_person(name)
    notify_roster_changed(app_state)
    return person


@router.get("/api/people/{person_id}")
def get_person(person_id: UUID, app_state: AppStateDependency) -> dict:
    person = app_state.roster.get_person(str(person_id))
    if person is None:
        raise ApiError.not_found("person")
    return person


@router.patch("/api/people/{person_id}")
def rename_person(person_id: UUID, name_request: NameRequest, app_state: AppStateDependency) -> dict:
    new_name = validate_name(name_request.name)
    person_with_that_name = app_state.roster.find_person_id_by_name(new_name)
    if person_with_that_name and person_with_that_name != str(person_id):
        raise ApiError.conflict(f"{new_name} is already enrolled")
    person = app_state.roster.rename_person(str(person_id), new_name)
    if person is None:
        raise ApiError.not_found("person")
    notify_roster_changed(app_state)
    return person


@router.delete("/api/people/{person_id}", status_code=204)
def delete_person(person_id: UUID, app_state: AppStateDependency) -> Response:
    if not app_state.roster.remove_person(str(person_id)):
        raise ApiError.not_found("person")
    notify_roster_changed(app_state)
    return Response(status_code=204)


@router.post("/api/people/{person_id}/samples")
def add_reference_photos(
    person_id: UUID,
    app_state: AppStateDependency,
    uploaded_images: Annotated[list[UploadFile] | None, File(alias="image")] = None,
    source: Annotated[str, Form()] = "upload",
) -> dict:
    """Adds the largest face in each image as a reference photo. Images that fail are
    listed under "rejected" instead of failing the whole request."""
    person_id_text = str(person_id)
    if app_state.roster.get_person(person_id_text) is None:
        raise ApiError.not_found("person")
    if not uploaded_images:
        raise ApiError.bad_request("send one or more images as multipart files named `image`")
    if source not in ALLOWED_REFERENCE_PHOTO_SOURCES:
        source = "upload"

    added_reference_photos = []
    rejected_files = []
    for uploaded_image in uploaded_images:
        filename = uploaded_image.filename or "image"
        try:
            reference_photo, warning = enroll_reference_photo(
                app_state, person_id_text, uploaded_image.file.read(), source
            )
            added_reference_photos.append({"file": filename, "sample": reference_photo, "warning": warning})
        except (ValueError, cv2.error) as error:
            rejected_files.append({"file": filename, "error": str(error)})

    person = app_state.roster.get_person(person_id_text)
    if person is None:
        raise ApiError.not_found("person")
    notify_roster_changed(app_state)
    return {"added": added_reference_photos, "rejected": rejected_files, "person": person}


def enroll_reference_photo(
    app_state: AppState, person_id: str, image_bytes: bytes, source: str
) -> tuple[dict, str | None]:
    """Keeps the largest face in the image as a reference photo, with a warning when something looks off."""
    image = decode_image(image_bytes)
    detected_faces = app_state.face_analyzer.detect_faces(image)
    if not detected_faces:
        raise ValueError("no face found - try a brighter, front-facing photo")
    largest_face = max(detected_faces, key=lambda face: face.area)
    if largest_face.width < MINIMUM_REFERENCE_FACE_WIDTH:
        raise ValueError(f"face is only {largest_face.width:.0f}px wide - use a closer photo")
    embedding = app_state.face_analyzer.compute_embedding(image, largest_face)
    thumbnail_jpeg = create_face_thumbnail(image, largest_face)

    warning = None
    if len(detected_faces) > 1:
        warning = f"{len(detected_faces)} faces in this photo - used the largest"
    closest_match = app_state.roster.find_closest_person(embedding)
    lookalike_threshold = app_state.settings.match_threshold + LOOKALIKE_WARNING_MARGIN
    if closest_match and closest_match.person_id != person_id and closest_match.similarity >= lookalike_threshold:
        warning = f"this face looks a lot like {closest_match.name} ({closest_match.similarity * 100:.0f}%)"

    reference_photo = app_state.roster.add_reference_photo(person_id, embedding, thumbnail_jpeg, source)
    if reference_photo is None:
        raise ValueError("person was deleted")
    return reference_photo, warning


@router.delete("/api/people/{person_id}/samples/{reference_photo_id}", status_code=204)
def delete_reference_photo(person_id: UUID, reference_photo_id: UUID, app_state: AppStateDependency) -> Response:
    if not app_state.roster.remove_reference_photo(str(person_id), str(reference_photo_id)):
        raise ApiError.not_found("sample")
    notify_roster_changed(app_state)
    return Response(status_code=204)


@router.get("/api/people/{person_id}/samples/{reference_photo_id}/image")
def get_reference_photo_image(person_id: UUID, reference_photo_id: UUID, app_state: AppStateDependency) -> FileResponse:
    thumbnail_path = app_state.roster.reference_photo_path(str(person_id), str(reference_photo_id))
    if not thumbnail_path.exists():
        raise ApiError.not_found("sample")
    return FileResponse(thumbnail_path, media_type="image/jpeg", headers=CACHE_FOREVER_HEADERS)
