"""Shared test helpers.

The model tests use the YuNet and SFace files in ../models and the two people in
samples/bus.jpg, enlarged so their faces are big enough to enroll.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.model_downloads import FACE_DETECTOR_MODEL, FACE_RECOGNIZER_MODEL

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIRECTORY = REPOSITORY_ROOT / "models"
BUS_PHOTO_PATH = REPOSITORY_ROOT / "samples" / "bus.jpg"

# The two faces in bus.jpg as [left, top, width, height].
FACE_BOXES_IN_BUS_PHOTO = {"left": (113, 415, 42, 54), "right": (268, 423, 38, 50)}

requires_face_models = pytest.mark.skipif(
    not all((MODELS_DIRECTORY / model.filename).exists() for model in (FACE_DETECTOR_MODEL, FACE_RECOGNIZER_MODEL)),
    reason="needs the YuNet and SFace files in models/ (start the server once to download them)",
)


def face_close_up(which_person: str, zoom: float = 4.0, mirror: bool = False) -> np.ndarray:
    """A close-up of one person from bus.jpg, enlarged `zoom` times."""
    bus_photo = cv2.imread(str(BUS_PHOTO_PATH))
    left, top, width, height = FACE_BOXES_IN_BUS_PHOTO[which_person]
    crop = bus_photo[top - height : top + 2 * height, left - width : left + 2 * width]
    enlarged_crop = cv2.resize(crop, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_CUBIC)
    return cv2.flip(enlarged_crop, 1) if mirror else enlarged_crop


def place_side_by_side(*images: np.ndarray) -> np.ndarray:
    """One picture with the images next to each other, like a small class."""
    tallest_height = max(image.shape[0] for image in images)
    padded_images = [
        cv2.copyMakeBorder(image, 0, tallest_height - image.shape[0], 20, 20, cv2.BORDER_CONSTANT)
        for image in images
    ]
    return np.hstack(padded_images)


def encode_test_jpeg(image: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()
