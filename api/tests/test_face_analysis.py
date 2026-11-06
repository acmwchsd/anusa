import cv2
import numpy as np
import pytest

from app.face_analysis import (
    DetectedFace,
    FaceAnalyzer,
    cosine_similarity,
    create_face_thumbnail,
    decode_image,
    intersection_over_union,
    merge_detection_passes,
)
from app.model_downloads import FACE_DETECTOR_MODEL, FACE_RECOGNIZER_MODEL

from .conftest import BUS_PHOTO_PATH, MODELS_DIRECTORY, encode_test_jpeg, face_close_up, requires_face_models


def square_face(left: float, side: float, confidence: float = 0.9) -> DetectedFace:
    return DetectedFace(bounding_box=[left, 0.0, side, side], landmarks=[[0.0, 0.0]] * 5, confidence=confidence)


def test_intersection_over_union():
    assert intersection_over_union([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)
    assert intersection_over_union([0, 0, 10, 10], [20, 20, 5, 5]) == 0.0
    assert intersection_over_union([0, 0, 10, 10], [5, 0, 10, 10]) == pytest.approx(1 / 3)


def test_a_big_face_keeps_the_box_from_the_smaller_pass_however_confident_the_other():
    # 100 px at full size is 2.1 times off 48 px; at half size it is 50 px
    full_size_face = square_face(5, 90, confidence=0.95)
    half_size_face = square_face(0, 100, confidence=0.80)
    assert merge_detection_passes([(1.0, [full_size_face]), (0.5, [half_size_face])]) == [half_size_face]


def test_a_small_face_keeps_the_full_size_box():
    # 42 px at full size, but only 21 px (too blurry) at half size
    full_size_face = square_face(1, 42, confidence=0.80)
    half_size_face = square_face(0, 40, confidence=0.95)
    assert merge_detection_passes([(1.0, [full_size_face]), (0.5, [half_size_face])]) == [full_size_face]


def test_a_face_found_by_only_one_pass_is_kept():
    small_face_only_at_full_size = square_face(1000, 30)
    big_face_only_at_quarter_size = square_face(0, 300)
    merged_faces = merge_detection_passes(
        [(1.0, [small_face_only_at_full_size]), (0.25, [big_face_only_at_quarter_size])]
    )
    assert merged_faces == [big_face_only_at_quarter_size, small_face_only_at_full_size]


def test_decode_rejects_bytes_that_are_not_an_image():
    with pytest.raises(ValueError):
        decode_image(b"hello")


def test_thumbnail_is_a_square_jpeg_even_at_the_edge():
    image = np.zeros((300, 400, 3), np.uint8)
    face_in_corner = DetectedFace(bounding_box=[0.0, 0.0, 80.0, 100.0], landmarks=[[0.0, 0.0]] * 5, confidence=1.0)
    thumbnail = decode_image(create_face_thumbnail(image, face_in_corner))
    assert thumbnail.shape == (256, 256, 3)


@pytest.fixture(scope="module")
def face_analyzer():
    return FaceAnalyzer(
        MODELS_DIRECTORY / FACE_DETECTOR_MODEL.filename, MODELS_DIRECTORY / FACE_RECOGNIZER_MODEL.filename
    )


@requires_face_models
def test_finds_both_faces_in_the_bus_photo(face_analyzer):
    detected_faces = face_analyzer.detect_faces(cv2.imread(str(BUS_PHOTO_PATH)))
    assert len(detected_faces) == 2
    assert all(face.confidence > 0.7 for face in detected_faces)


@requires_face_models
def test_finds_small_and_big_faces_in_one_big_photo(face_analyzer):
    """A 2400 px wide picture with one face close up and one far away."""
    canvas = np.full((1400, 2400, 3), 90, np.uint8)
    near_face = face_close_up("left", zoom=6.0)  # about 250 px wide
    far_face = face_close_up("right", zoom=0.75)  # about 28 px wide
    canvas[100 : 100 + near_face.shape[0], 100 : 100 + near_face.shape[1]] = near_face
    canvas[600 : 600 + far_face.shape[0], 1800 : 1800 + far_face.shape[1]] = far_face
    face_widths = sorted(face.width for face in face_analyzer.detect_faces(canvas))
    assert len(face_widths) == 2
    assert face_widths[0] < 40
    # measured in a smaller copy: the full-size pass alone makes it about 214 px
    assert face_widths[1] == pytest.approx(6.0 * 42.2, rel=0.05)


@requires_face_models
def test_a_face_filling_the_frame_is_measured_at_full_size(face_analyzer):
    """A face 330 px wide in a 960 px frame is too big to measure at 960 or 640 px."""
    close_up = face_close_up("left", zoom=330 / 42.2)
    padded = cv2.copyMakeBorder(close_up, 540, 540, 960, 960, cv2.BORDER_CONSTANT, value=(90, 90, 90))
    center_y, center_x = padded.shape[0] // 2, padded.shape[1] // 2
    frame = padded[center_y - 270 : center_y + 270, center_x - 480 : center_x + 480]
    (big_face,) = [face for face in face_analyzer.detect_faces(frame) if face.width > 100]
    assert big_face.width == pytest.approx(330, rel=0.1)


@requires_face_models
def test_the_same_person_is_more_alike_than_two_different_people(face_analyzer):
    def embedding_of(image):
        image = decode_image(encode_test_jpeg(image))
        (face,) = face_analyzer.detect_faces(image)
        return face_analyzer.compute_embedding(image, face)

    left_person = embedding_of(face_close_up("left"))
    left_person_mirrored = embedding_of(face_close_up("left", zoom=3.0, mirror=True))
    right_person = embedding_of(face_close_up("right"))
    assert np.linalg.norm(left_person) == pytest.approx(1.0, abs=1e-5)
    assert cosine_similarity(left_person, left_person_mirrored) > 0.5
    assert cosine_similarity(left_person, right_person) < cosine_similarity(left_person, left_person_mirrored)
