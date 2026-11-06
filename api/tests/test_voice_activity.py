import io
import wave

import numpy as np

from app.voice_activity import MAXIMUM_UTTERANCE_SAMPLES, SAMPLE_RATE_HZ, UtteranceDetector, samples_to_wav_bytes


def tone(duration_ms: int, amplitude: float) -> np.ndarray:
    times = np.arange(SAMPLE_RATE_HZ * duration_ms // 1000) / SAMPLE_RATE_HZ
    return (amplitude * np.sin(2 * np.pi * 220 * times)).astype(np.int16)


def test_cuts_speech_between_silences():
    utterance_detector = UtteranceDetector()
    quiet_room, spoken_word = tone(1000, 20), tone(800, 8000)
    utterances = utterance_detector.add_audio(np.concatenate([quiet_room, spoken_word, quiet_room]))
    assert len(utterances) == 1
    utterance_seconds = len(utterances[0]) / SAMPLE_RATE_HZ
    assert 1.0 <= utterance_seconds < 1.8


def test_ignores_clicks():
    utterance_detector = UtteranceDetector()
    audio = np.concatenate([tone(500, 20), tone(40, 8000), tone(1000, 20)])
    assert utterance_detector.add_audio(audio) == []


def test_splits_long_speech_with_overlap():
    utterance_detector = UtteranceDetector()
    utterances = utterance_detector.add_audio(tone(11_000, 8000))
    assert [len(utterance) for utterance in utterances] == [MAXIMUM_UTTERANCE_SAMPLES, MAXIMUM_UTTERANCE_SAMPLES]


def test_audio_can_arrive_in_any_chunk_size():
    whole_audio_detector, chunked_audio_detector = UtteranceDetector(), UtteranceDetector()
    audio = np.concatenate([tone(1000, 20), tone(800, 8000), tone(1000, 20)])
    expected_utterances = whole_audio_detector.add_audio(audio)
    chunked_utterances = []
    for chunk_start in range(0, len(audio), 1234):
        chunked_utterances += chunked_audio_detector.add_audio(audio[chunk_start : chunk_start + 1234])
    assert [len(utterance) for utterance in chunked_utterances] == [
        len(utterance) for utterance in expected_utterances
    ]


def test_wav_is_well_formed():
    wav_bytes = samples_to_wav_bytes(np.array([0, 1, -1], np.int16))
    with wave.open(io.BytesIO(wav_bytes)) as wav_file:
        wav_format = (wav_file.getnchannels(), wav_file.getsampwidth(), wav_file.getframerate(), wav_file.getnframes())
        assert wav_format == (1, 2, SAMPLE_RATE_HZ, 3)
    assert len(wav_bytes) == 44 + 6
