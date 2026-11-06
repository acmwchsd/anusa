import asyncio
import importlib.util

import numpy as np
import pytest

from app.model_downloads import WHISPER_BASE_ENGLISH_MODEL
from app.transcription import LocalWhisperTranscriber, remove_non_speech_annotations
from app.voice_activity import SAMPLE_RATE_HZ

from .conftest import MODELS_DIRECTORY

WHISPER_MODEL_PATH = MODELS_DIRECTORY / WHISPER_BASE_ENGLISH_MODEL.filename

requires_whisper = pytest.mark.skipif(
    importlib.util.find_spec("pywhispercpp") is None or not WHISPER_MODEL_PATH.exists(),
    reason="needs pywhispercpp and models/ggml-base.en.bin (start the server once to download it)",
)


def test_keeps_only_the_words():
    assert remove_non_speech_annotations(" [BLANK_AUDIO]") == ""
    assert (
        remove_non_speech_annotations(" Okay (laughs) everyone, *sighs* Techpreneur.") == "Okay everyone, Techpreneur."
    )
    assert remove_non_speech_annotations("[Music] (upbeat music)") == ""


@requires_whisper
def test_whisper_cpp_hears_no_words_in_silence_or_a_hum():
    transcriber = LocalWhisperTranscriber(WHISPER_MODEL_PATH, thread_count=2)
    speech_status = asyncio.run(transcriber.check_status())
    assert (speech_status["available"], speech_status["model_version"]) == (True, "whisper.cpp/ggml-base.en.bin")

    silence = np.zeros(SAMPLE_RATE_HZ * 2, np.int16)
    assert asyncio.run(transcriber.transcribe(silence)) == ""

    times = np.arange(SAMPLE_RATE_HZ) / SAMPLE_RATE_HZ
    hum = (8000 * np.sin(2 * np.pi * 220 * times)).astype(np.int16)
    assert asyncio.run(transcriber.transcribe(hum)) == ""
