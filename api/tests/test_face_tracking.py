from app.face_analysis import DetectedFace
from app.face_tracking import MAXIMUM_MISSED_FRAMES, FaceTracker


def face_at(left: float) -> DetectedFace:
    return DetectedFace(bounding_box=[left, 10.0, 50.0, 60.0], landmarks=[[0.0, 0.0]] * 5, confidence=0.9)


def test_keeps_identity_while_moving_and_forgets_when_gone():
    face_tracker = FaceTracker()
    first_frame_tracks = face_tracker.update([face_at(0.0), face_at(200.0)])
    left_track_id, right_track_id = first_frame_tracks[0].track_id, first_frame_tracks[1].track_id

    # both moved a little, and arrive in the other order
    second_frame_tracks = face_tracker.update([face_at(205.0), face_at(4.0)])
    assert [track.track_id for track in second_frame_tracks] == [right_track_id, left_track_id]

    # the right face leaves; the left one stays
    for _ in range(MAXIMUM_MISSED_FRAMES + 1):
        face_tracker.update([face_at(8.0)])
    assert [track.track_id for track in face_tracker.tracks] == [left_track_id]


def test_a_new_face_gets_a_new_track():
    face_tracker = FaceTracker()
    (first_track,) = face_tracker.update([face_at(0.0)])
    (second_track,) = face_tracker.update([face_at(400.0)])
    assert first_track.track_id != second_track.track_id
