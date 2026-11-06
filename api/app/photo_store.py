import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .class_roster import ClassRoster
from .face_analysis import EMBEDDING_LENGTH, DetectedFace
from .json_files import read_json_file, write_json_file_atomically

logger = logging.getLogger(__name__)


@dataclass
class PhotoFace:
    bounding_box: list[float]
    landmarks: list[list[float]]
    confidence: float
    embedding: list[float]
    assigned_person_id: str | None = None

    @classmethod
    def from_detection(cls, face: DetectedFace, embedding: np.ndarray | None) -> "PhotoFace":
        return cls(
            bounding_box=[round(value, 2) for value in face.bounding_box],
            landmarks=[[round(x, 2), round(y, 2)] for x, y in face.landmarks],
            confidence=round(face.confidence, 4),
            embedding=[] if embedding is None else [round(float(value), 6) for value in embedding],
        )

    def to_detection(self) -> DetectedFace:
        return DetectedFace(bounding_box=self.bounding_box, landmarks=self.landmarks, confidence=self.confidence)

    def to_file_json(self) -> dict:
        return {
            "bbox": self.bounding_box,
            "landmarks": self.landmarks,
            "score": self.confidence,
            "embedding": self.embedding,
            "assigned": self.assigned_person_id,
        }

    @classmethod
    def from_file_json(cls, data: dict) -> "PhotoFace":
        return cls(
            bounding_box=data["bbox"],
            landmarks=data["landmarks"],
            confidence=data["score"],
            embedding=data["embedding"],
            assigned_person_id=data.get("assigned"),
        )

    def to_api_json(self, face_index: int, roster: ClassRoster, match_threshold: float) -> dict:
        """Who this face is: the teacher's label if there is one, otherwise the closest person above the threshold."""
        unnamed_face = {
            "index": face_index,
            "bbox": self.bounding_box,
            "score": self.confidence,
            "person_id": None,
            "name": None,
            "similarity": None,
            "assigned": False,
        }
        assigned_person = roster.get_person(self.assigned_person_id) if self.assigned_person_id else None
        if assigned_person:
            return {**unnamed_face, "person_id": assigned_person["id"], "name": assigned_person["name"], "assigned": True}

        if len(self.embedding) == EMBEDDING_LENGTH:
            closest_match = roster.find_closest_person(np.array(self.embedding, dtype=np.float32))
            if closest_match and closest_match.similarity >= match_threshold:
                return {
                    **unnamed_face,
                    "person_id": closest_match.person_id,
                    "name": closest_match.name,
                    "similarity": closest_match.similarity,
                }
        return unnamed_face


@dataclass
class Photo:
    photo_id: str
    taken_at: str
    width: int
    height: int
    file_size_bytes: int
    trigger: str
    heard_text: str | None
    faces: list[PhotoFace]

    def to_file_json(self) -> dict:
        return {
            "id": self.photo_id,
            "taken_at": self.taken_at,
            "width": self.width,
            "height": self.height,
            "bytes": self.file_size_bytes,
            "trigger": self.trigger,
            "heard": self.heard_text,
            "faces": [face.to_file_json() for face in self.faces],
        }

    @classmethod
    def from_file_json(cls, data: dict) -> "Photo":
        return cls(
            photo_id=data["id"],
            taken_at=data["taken_at"],
            width=data["width"],
            height=data["height"],
            file_size_bytes=data["bytes"],
            trigger=data["trigger"],
            heard_text=data.get("heard"),
            faces=[PhotoFace.from_file_json(face_data) for face_data in data["faces"]],
        )

    def to_api_json(self, roster: ClassRoster, match_threshold: float) -> dict:
        """The photo with its faces named, sorted from left to right."""
        face_views = [
            face.to_api_json(face_index, roster, match_threshold) for face_index, face in enumerate(self.faces)
        ]
        face_views.sort(key=lambda face_view: face_view["bbox"][0])
        people_in_photo: list[str] = []
        for face_view in face_views:
            if face_view["name"] and face_view["name"] not in people_in_photo:
                people_in_photo.append(face_view["name"])
        return {
            "id": self.photo_id,
            "taken_at": self.taken_at,
            "width": self.width,
            "height": self.height,
            "bytes": self.file_size_bytes,
            "trigger": self.trigger,
            "heard": self.heard_text,
            "url": f"/api/photos/{self.photo_id}/image",
            "faces": face_views,
            "people": people_in_photo,
        }


class PhotoStore:
    def __init__(self, data_directory: Path):
        self._photos_directory = data_directory / "photos"
        self._photos_directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._photos: list[Photo] = []
        for metadata_path in self._photos_directory.glob("*.json"):
            try:
                self._photos.append(Photo.from_file_json(read_json_file(metadata_path, None)))
            except (ValueError, KeyError, TypeError) as error:
                logger.warning("skipping %s: %s", metadata_path, error)
        self._photos.sort(key=lambda photo: photo.taken_at, reverse=True)

    def list_newest_first(self) -> list[Photo]:
        return list(self._photos)

    def get_photo(self, photo_id: str) -> Photo | None:
        return next((photo for photo in self._photos if photo.photo_id == photo_id), None)

    def image_path(self, photo_id: str) -> Path:
        return self._photos_directory / f"{photo_id}.jpg"

    def _metadata_path(self, photo_id: str) -> Path:
        return self._photos_directory / f"{photo_id}.json"

    def add_photo(self, photo: Photo, jpeg_bytes: bytes) -> None:
        with self._lock:
            self.image_path(photo.photo_id).write_bytes(jpeg_bytes)
            write_json_file_atomically(self._metadata_path(photo.photo_id), photo.to_file_json())
            self._photos.insert(0, photo)

    def assign_face(self, photo_id: str, face_index: int, person_id: str | None) -> Photo | None:
        """Labels a face as a person; None clears the label."""
        with self._lock:
            photo = self.get_photo(photo_id)
            if photo is None or not 0 <= face_index < len(photo.faces):
                return None
            photo.faces[face_index].assigned_person_id = person_id
            write_json_file_atomically(self._metadata_path(photo_id), photo.to_file_json())
            return photo

    def remove_photo(self, photo_id: str) -> bool:
        with self._lock:
            photo = self.get_photo(photo_id)
            if photo is None:
                return False
            self._photos.remove(photo)
        self.image_path(photo_id).unlink(missing_ok=True)
        self._metadata_path(photo_id).unlink(missing_ok=True)
        return True
