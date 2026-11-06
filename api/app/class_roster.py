import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .face_analysis import EMBEDDING_LENGTH
from .json_files import current_utc_timestamp, generate_id, read_json_file, write_json_file_atomically


@dataclass
class ReferencePhoto:
    photo_id: str
    created_at: str
    # "upload", "camera" or "photo:<photo id>"
    source: str
    embedding: list[float]

    def to_api_json(self) -> dict:
        return {"id": self.photo_id, "created_at": self.created_at, "source": self.source}

    def to_file_json(self) -> dict:
        return {**self.to_api_json(), "embedding": self.embedding}

    @classmethod
    def from_file_json(cls, data: dict) -> "ReferencePhoto":
        return cls(
            photo_id=data["id"],
            created_at=data["created_at"],
            source=data["source"],
            embedding=data.get("embedding", []),
        )


@dataclass
class Person:
    person_id: str
    name: str
    created_at: str
    reference_photos: list[ReferencePhoto]

    def to_api_json(self) -> dict:
        return {
            "id": self.person_id,
            "name": self.name,
            "created_at": self.created_at,
            "samples": [reference_photo.to_api_json() for reference_photo in self.reference_photos],
        }

    def to_file_json(self) -> dict:
        return {
            **self.to_api_json(),
            "samples": [reference_photo.to_file_json() for reference_photo in self.reference_photos],
        }

    @classmethod
    def from_file_json(cls, data: dict) -> "Person":
        return cls(
            person_id=data["id"],
            name=data["name"],
            created_at=data["created_at"],
            reference_photos=[ReferencePhoto.from_file_json(photo_data) for photo_data in data["samples"]],
        )


@dataclass
class ClosestMatch:
    person_id: str
    name: str
    similarity: float


class ClassRoster:
    def __init__(self, data_directory: Path):
        self._roster_file = data_directory / "gallery.json"
        self._thumbnails_directory = data_directory / "people"
        self._lock = threading.RLock()
        saved_roster = read_json_file(self._roster_file, {"people": []})
        self._people = [Person.from_file_json(person_data) for person_data in saved_roster["people"]]
        # Increases on every change, so pages know when to fetch the roster again.
        self.version = 1
        self._rebuild_embedding_index()

    def list_people(self) -> list[dict]:
        people_sorted_by_name = sorted(self._people, key=lambda person: person.name.lower())
        return [person.to_api_json() for person in people_sorted_by_name]

    def get_person(self, person_id: str) -> dict | None:
        person = self._find_person(person_id)
        return person.to_api_json() if person else None

    def find_person_id_by_name(self, name: str) -> str | None:
        normalized_name = name.strip().lower()
        return next((person.person_id for person in self._people if person.name.lower() == normalized_name), None)

    def count_reference_photos(self) -> int:
        return sum(len(person.reference_photos) for person in self._people)

    def reference_photo_path(self, person_id: str, photo_id: str) -> Path:
        return self._thumbnails_directory / person_id / f"{photo_id}.jpg"

    def find_closest_person(self, embedding: np.ndarray) -> ClosestMatch | None:
        """The person whose best reference photo is most similar, however low the similarity."""
        embedding_matrix, row_owners = self._embedding_index
        if not row_owners:
            return None
        similarities = embedding_matrix @ embedding
        best_row = int(np.argmax(similarities))
        person_id, name = row_owners[best_row]
        return ClosestMatch(person_id=person_id, name=name, similarity=float(similarities[best_row]))

    def add_person(self, name: str) -> dict:
        person = Person(person_id=generate_id(), name=name.strip(), created_at=current_utc_timestamp(), reference_photos=[])
        with self._lock:
            self._people.append(person)
            self._save()
        return person.to_api_json()

    def rename_person(self, person_id: str, new_name: str) -> dict | None:
        with self._lock:
            person = self._find_person(person_id)
            if person is None:
                return None
            person.name = new_name.strip()
            self._save()
            return person.to_api_json()

    def remove_person(self, person_id: str) -> bool:
        with self._lock:
            person = self._find_person(person_id)
            if person is None:
                return False
            self._people.remove(person)
            self._save()
        shutil.rmtree(self._thumbnails_directory / person_id, ignore_errors=True)
        return True

    def add_reference_photo(
        self, person_id: str, embedding: np.ndarray, thumbnail_jpeg: bytes, source: str
    ) -> dict | None:
        with self._lock:
            person = self._find_person(person_id)
            if person is None:
                return None
            reference_photo = ReferencePhoto(
                photo_id=generate_id(),
                created_at=current_utc_timestamp(),
                source=source,
                embedding=[round(float(value), 6) for value in embedding],
            )
            thumbnail_path = self.reference_photo_path(person_id, reference_photo.photo_id)
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail_path.write_bytes(thumbnail_jpeg)
            person.reference_photos.append(reference_photo)
            self._save()
            return reference_photo.to_api_json()

    def remove_reference_photo(self, person_id: str, photo_id: str) -> bool:
        with self._lock:
            person = self._find_person(person_id)
            reference_photo = (
                next((photo for photo in person.reference_photos if photo.photo_id == photo_id), None)
                if person
                else None
            )
            if reference_photo is None:
                return False
            person.reference_photos.remove(reference_photo)
            self._save()
        self.reference_photo_path(person_id, photo_id).unlink(missing_ok=True)
        return True

    def _find_person(self, person_id: str) -> Person | None:
        return next((person for person in self._people if person.person_id == person_id), None)

    def _save(self) -> None:
        self.version += 1
        write_json_file_atomically(self._roster_file, {"people": [person.to_file_json() for person in self._people]})
        self._rebuild_embedding_index()

    def _rebuild_embedding_index(self) -> None:
        embedding_rows = []
        row_owners = []
        for person in self._people:
            for reference_photo in person.reference_photos:
                if len(reference_photo.embedding) == EMBEDDING_LENGTH:
                    embedding_rows.append(reference_photo.embedding)
                    row_owners.append((person.person_id, person.name))
        embedding_matrix = np.array(embedding_rows, dtype=np.float32).reshape(-1, EMBEDDING_LENGTH)
        # Assigned as one tuple, so a reader never sees a matrix and owners from different versions.
        self._embedding_index = (embedding_matrix, row_owners)
