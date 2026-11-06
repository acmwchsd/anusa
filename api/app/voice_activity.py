import io
import wave
from collections import deque

import numpy as np

SAMPLE_RATE_HZ = 16_000
FRAME_DURATION_MS = 20
FRAME_LENGTH_SAMPLES = SAMPLE_RATE_HZ * FRAME_DURATION_MS // 1000
PRE_ROLL_FRAMES = 15
VOICED_FRAMES_TO_START_UTTERANCE = 3
SILENCE_TO_END_UTTERANCE_MS = 600
MINIMUM_SPEECH_MS = 200
MAXIMUM_UTTERANCE_SAMPLES = SAMPLE_RATE_HZ * 5
CARRY_OVER_SAMPLES = SAMPLE_RATE_HZ
MINIMUM_SPEECH_LOUDNESS = 350.0
SPEECH_TO_NOISE_RATIO = 3
NOISE_FLOOR_SMOOTHING = 0.97
INITIAL_NOISE_FLOOR = 150.0


class UtteranceDetector:
    def __init__(self) -> None:
        self.is_speaking = False
        self._unprocessed_samples = np.zeros(0, np.int16)
        self._pre_roll_frames: deque[np.ndarray] = deque(maxlen=PRE_ROLL_FRAMES)
        self._utterance_frames: list[np.ndarray] = []
        self._utterance_length_samples = 0
        self._consecutive_voiced_frames = 0
        self._silence_duration_ms = 0
        self._speech_duration_ms = 0
        self._noise_floor = INITIAL_NOISE_FLOOR

    def add_audio(self, samples: np.ndarray) -> list[np.ndarray]:
        self._unprocessed_samples = np.concatenate([self._unprocessed_samples, samples])
        finished_utterances = []
        while len(self._unprocessed_samples) >= FRAME_LENGTH_SAMPLES:
            frame = self._unprocessed_samples[:FRAME_LENGTH_SAMPLES]
            self._unprocessed_samples = self._unprocessed_samples[FRAME_LENGTH_SAMPLES:]
            finished_utterance = self._process_frame(frame)
            if finished_utterance is not None:
                finished_utterances.append(finished_utterance)
        return finished_utterances

    def _process_frame(self, frame: np.ndarray) -> np.ndarray | None:
        loudness = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        is_voiced = loudness > max(self._noise_floor * SPEECH_TO_NOISE_RATIO, MINIMUM_SPEECH_LOUDNESS)
        if not is_voiced:
            self._noise_floor = NOISE_FLOOR_SMOOTHING * self._noise_floor + (1 - NOISE_FLOOR_SMOOTHING) * loudness

        if self.is_speaking:
            return self._continue_utterance(frame, is_voiced)
        self._wait_for_speech(frame, is_voiced)
        return None

    def _wait_for_speech(self, frame: np.ndarray, is_voiced: bool) -> None:
        self._consecutive_voiced_frames = self._consecutive_voiced_frames + 1 if is_voiced else 0
        self._pre_roll_frames.append(frame)
        if self._consecutive_voiced_frames < VOICED_FRAMES_TO_START_UTTERANCE:
            return
        self.is_speaking = True
        self._utterance_frames = list(self._pre_roll_frames)
        self._utterance_length_samples = sum(len(pre_roll_frame) for pre_roll_frame in self._utterance_frames)
        self._pre_roll_frames.clear()
        self._speech_duration_ms = self._consecutive_voiced_frames * FRAME_DURATION_MS
        self._silence_duration_ms = 0

    def _continue_utterance(self, frame: np.ndarray, is_voiced: bool) -> np.ndarray | None:
        self._utterance_frames.append(frame)
        self._utterance_length_samples += len(frame)
        if is_voiced:
            self._silence_duration_ms = 0
            self._speech_duration_ms += FRAME_DURATION_MS
        else:
            self._silence_duration_ms += FRAME_DURATION_MS

        if self._silence_duration_ms >= SILENCE_TO_END_UTTERANCE_MS:
            return self._end_utterance()
        if self._utterance_length_samples >= MAXIMUM_UTTERANCE_SAMPLES:
            return self._cut_long_utterance()
        return None

    def _end_utterance(self) -> np.ndarray | None:
        self.is_speaking = False
        self._consecutive_voiced_frames = 0
        utterance = np.concatenate(self._utterance_frames)
        self._utterance_frames = []
        self._utterance_length_samples = 0
        return utterance if self._speech_duration_ms >= MINIMUM_SPEECH_MS else None

    def _cut_long_utterance(self) -> np.ndarray:
        utterance = np.concatenate(self._utterance_frames)
        carried_over_audio = utterance[-CARRY_OVER_SAMPLES:]
        self._utterance_frames = [carried_over_audio]
        self._utterance_length_samples = len(carried_over_audio)
        self._speech_duration_ms = 0
        return utterance


def samples_to_wav_bytes(samples: np.ndarray) -> bytes:
    """Wraps 16-bit mono samples in an in-memory WAV file."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE_HZ)
        wav_file.writeframes(samples.astype("<i2").tobytes())
    return wav_buffer.getvalue()
