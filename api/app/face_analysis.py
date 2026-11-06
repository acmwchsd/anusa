import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

MINIMUM_DETECTION_CONFIDENCE = 0.7
DUPLICATE_OVERLAP_THRESHOLD = 0.3
MAXIMUM_DETECTIONS_PER_IMAGE = 5000
DETECTION_PASS_LONGEST_SIDES = (2560, 640, 320)
IDEAL_DETECTION_FACE_WIDTH = 48.0
MINIMUM_IDENTIFIABLE_FACE_WIDTH = 24.0
LANDMARK_COUNT = 5
EMBEDDING_LENGTH = 128
THUMBNAIL_SIZE = 256
THUMBNAIL_JPEG_QUALITY = 88
THUMBNAIL_MARGIN_FACTOR = 1.6


@dataclass
class DetectedFace:
    bounding_box: list[float]
    landmarks: list[list[float]]
    confidence: float

    @property
    def width(self) -> float:
        return self.bounding_box[2]

    @property
    def area(self) -> float:
        return self.bounding_box[2] * self.bounding_box[3]

    @property
    def is_identifiable(self) -> bool:
        return self.width >= MINIMUM_IDENTIFIABLE_FACE_WIDTH

    def scaled(self, scale_factor: float) -> "DetectedFace":
        return DetectedFace(
            bounding_box=[value * scale_factor for value in self.bounding_box],
            landmarks=[[x * scale_factor, y * scale_factor] for x, y in self.landmarks],
            confidence=self.confidence,
        )

    @classmethod
    def from_yunet_row(cls, row: np.ndarray, image_width: int, image_height: int) -> "DetectedFace":
        """Parses one YuNet output row (x, y, width, height, 5 landmark points, confidence),
        clipping the box to the image because a face can extend past the edge."""
        left = max(float(row[0]), 0.0)
        top = max(float(row[1]), 0.0)
        right = min(float(row[0] + row[2]), image_width)
        bottom = min(float(row[1] + row[3]), image_height)
        landmarks = [[float(row[4 + 2 * index]), float(row[5 + 2 * index])] for index in range(LANDMARK_COUNT)]
        return cls(bounding_box=[left, top, right - left, bottom - top], landmarks=landmarks, confidence=float(row[14]))

    def to_yunet_row(self) -> np.ndarray:
        """The 15-number YuNet format that SFace's alignCrop expects."""
        flattened_landmarks = [coordinate for point in self.landmarks for coordinate in point]
        return np.array([*self.bounding_box, *flattened_landmarks, self.confidence], dtype=np.float32)


def intersection_over_union(first_box: list[float], second_box: list[float]) -> float:
    """Overlap of two [left, top, width, height] boxes: 0 when apart, 1 when identical."""
    overlap_left = max(first_box[0], second_box[0])
    overlap_top = max(first_box[1], second_box[1])
    overlap_right = min(first_box[0] + first_box[2], second_box[0] + second_box[2])
    overlap_bottom = min(first_box[1] + first_box[3], second_box[1] + second_box[3])
    overlap_area = max(overlap_right - overlap_left, 0.0) * max(overlap_bottom - overlap_top, 0.0)
    union_area = first_box[2] * first_box[3] + second_box[2] * second_box[3] - overlap_area
    return overlap_area / union_area if union_area > 0 else 0.0


def merge_detection_passes(detection_passes: list[tuple[float, list[DetectedFace]]]) -> list[DetectedFace]:
    def distance_from_ideal_width(scale_factor: float, face: DetectedFace) -> float:
        width_in_pass = max(face.width * scale_factor, 1.0)
        return max(width_in_pass / IDEAL_DETECTION_FACE_WIDTH, IDEAL_DETECTION_FACE_WIDTH / width_in_pass)

    candidates = [
        (distance_from_ideal_width(scale_factor, face), face)
        for scale_factor, faces in detection_passes
        for face in faces
    ]
    candidates.sort(key=lambda candidate: candidate[0])

    kept_faces: list[DetectedFace] = []
    for _, face in candidates:
        overlaps_a_kept_face = any(
            intersection_over_union(kept_face.bounding_box, face.bounding_box) > DUPLICATE_OVERLAP_THRESHOLD
            for kept_face in kept_faces
        )
        if not overlaps_a_kept_face:
            kept_faces.append(face)
    return kept_faces


def normalize_to_unit_length(vector: np.ndarray) -> np.ndarray:
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


def cosine_similarity(first_embedding: np.ndarray, second_embedding: np.ndarray) -> float:
    return float(np.dot(first_embedding, second_embedding))


class FaceAnalyzer:
    def __init__(self, detector_model_path: Path, recognizer_model_path: Path):
        self._detector = cv2.FaceDetectorYN.create(
            str(detector_model_path),
            "",
            (640, 640),
            MINIMUM_DETECTION_CONFIDENCE,
            DUPLICATE_OVERLAP_THRESHOLD,
            MAXIMUM_DETECTIONS_PER_IMAGE,
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_model_path), "")
        self._detector_lock = threading.Lock()
        self._recognizer_lock = threading.Lock()
        self._warm_up()

    def _warm_up(self) -> None:
        blank_image = np.zeros((480, 640, 3), np.uint8)
        self.detect_faces(blank_image)
        typical_landmarks = [[38.0, 51.0], [73.0, 51.0], [56.0, 71.0], [41.0, 92.0], [70.0, 92.0]]
        typical_face = DetectedFace(bounding_box=[20.0, 20.0, 72.0, 90.0], landmarks=typical_landmarks, confidence=1.0)
        self.compute_embedding(blank_image, typical_face)

    def detect_faces(self, image: np.ndarray) -> list[DetectedFace]:
        image_height, image_width = image.shape[:2]
        longest_side = max(image_width, image_height)
        scale_factors = sorted(
            {min(1.0, pass_longest_side / longest_side) for pass_longest_side in DETECTION_PASS_LONGEST_SIDES},
            reverse=True,
        )
        return merge_detection_passes(
            [(scale_factor, self._detect_at_scale(image, scale_factor)) for scale_factor in scale_factors]
        )

    def _detect_at_scale(self, image: np.ndarray, scale_factor: float) -> list[DetectedFace]:
        if scale_factor != 1.0:
            image = cv2.resize(image, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA)
        image_height, image_width = image.shape[:2]
        with self._detector_lock:
            self._detector.setInputSize((image_width, image_height))
            _, detection_rows = self._detector.detect(image)
        if detection_rows is None:
            return []
        return [
            DetectedFace.from_yunet_row(row, image_width, image_height).scaled(1 / scale_factor)
            for row in detection_rows
        ]

    def compute_embedding(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        """Aligns the face to SFace's 112 x 112 template and returns a unit-length 128-number embedding."""
        with self._recognizer_lock:
            aligned_face = self._recognizer.alignCrop(image, face.to_yunet_row())
            embedding = self._recognizer.feature(aligned_face)[0]
        return normalize_to_unit_length(embedding)


def decode_image(image_bytes: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("not a readable image (JPEG, PNG or WebP)")
    return image


def encode_jpeg(image: np.ndarray, quality: int) -> bytes:
    succeeded, encoded_buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not succeeded:
        raise ValueError("could not encode the image as JPEG")
    return encoded_buffer.tobytes()


def create_face_thumbnail(image: np.ndarray, face: DetectedFace) -> bytes:
    image_height, image_width = image.shape[:2]
    box_left, box_top, box_width, box_height = face.bounding_box
    crop_side = max(max(box_width, box_height) * THUMBNAIL_MARGIN_FACTOR, 1.0)
    crop_side = min(crop_side, image_width, image_height)
    face_center_x = box_left + box_width / 2
    face_center_y = box_top + box_height / 2
    crop_left = int(min(max(face_center_x - crop_side / 2, 0), image_width - crop_side))
    crop_top = int(min(max(face_center_y - crop_side / 2, 0), image_height - crop_side))
    cropped_image = image[crop_top : crop_top + int(crop_side), crop_left : crop_left + int(crop_side)]
    thumbnail = cv2.resize(cropped_image, (THUMBNAIL_SIZE, THUMBNAIL_SIZE), interpolation=cv2.INTER_AREA)
    return encode_jpeg(thumbnail, THUMBNAIL_JPEG_QUALITY)
