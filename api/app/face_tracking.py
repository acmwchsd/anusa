from dataclasses import dataclass

import numpy as np

from .face_analysis import DetectedFace, intersection_over_union, normalize_to_unit_length

MINIMUM_TRACK_OVERLAP = 0.3
# Frames a track survives without its face, which covers blinks and a hand passing in front.
MAXIMUM_MISSED_FRAMES = 10
EMBEDDING_REFRESH_INTERVAL_FRAMES = 8


@dataclass
class FaceTrack:
    track_id: int
    bounding_box: list[float]
    last_seen_frame: int
    embedding: np.ndarray | None = None
    last_embedded_frame: int = 0

    def needs_new_embedding(self, current_frame: int) -> bool:
        return self.embedding is None or current_frame - self.last_embedded_frame >= EMBEDDING_REFRESH_INTERVAL_FRAMES

    def blend_in_embedding(self, new_embedding: np.ndarray, current_frame: int) -> None:
        if self.embedding is None:
            self.embedding = new_embedding
        else:
            self.embedding = normalize_to_unit_length(0.5 * self.embedding + 0.5 * new_embedding)
        self.last_embedded_frame = current_frame


class FaceTracker:
    def __init__(self) -> None:
        self.tracks: list[FaceTrack] = []
        self.frame_number = 0
        self._last_track_id = 0

    def update(self, faces: list[DetectedFace]) -> list[FaceTrack]:
        self.frame_number += 1
        face_tracks = self._match_faces_to_tracks(faces)
        for face_index, face in enumerate(faces):
            matched_track = face_tracks[face_index]
            if matched_track is None:
                face_tracks[face_index] = self._start_track(face)
            else:
                matched_track.bounding_box = face.bounding_box
                matched_track.last_seen_frame = self.frame_number
        self.tracks = [
            track for track in self.tracks if self.frame_number - track.last_seen_frame <= MAXIMUM_MISSED_FRAMES
        ]
        return face_tracks

    def _match_faces_to_tracks(self, faces: list[DetectedFace]) -> list[FaceTrack | None]:
        candidate_pairs = []
        for face_index, face in enumerate(faces):
            for track in self.tracks:
                overlap = intersection_over_union(face.bounding_box, track.bounding_box)
                if overlap >= MINIMUM_TRACK_OVERLAP:
                    candidate_pairs.append((overlap, face_index, track))
        candidate_pairs.sort(key=lambda pair: pair[0], reverse=True)

        face_tracks: list[FaceTrack | None] = [None] * len(faces)
        claimed_track_ids: set[int] = set()
        for _, face_index, track in candidate_pairs:
            if face_tracks[face_index] is None and track.track_id not in claimed_track_ids:
                face_tracks[face_index] = track
                claimed_track_ids.add(track.track_id)
        return face_tracks

    def _start_track(self, face: DetectedFace) -> FaceTrack:
        self._last_track_id += 1
        new_track = FaceTrack(
            track_id=self._last_track_id,
            bounding_box=face.bounding_box,
            last_seen_frame=self.frame_number,
        )
        self.tracks.append(new_track)
        return new_track
