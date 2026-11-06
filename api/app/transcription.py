import asyncio
import logging
import re
import threading
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from .voice_activity import samples_to_wav_bytes

SPEECH_API_REQUEST_TIMEOUT_SECONDS = 20
SPEECH_API_HEALTH_TIMEOUT_SECONDS = 3
MAXIMUM_SAMPLE_MAGNITUDE = 32768.0
NON_SPEECH_ANNOTATION_PATTERN = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")


def remove_non_speech_annotations(transcript: str) -> str:
    return " ".join(NON_SPEECH_ANNOTATION_PATTERN.sub(" ", transcript).split())


def unavailable_speech_status(error_message: str | None = None) -> dict:
    return {"url": None, "available": False, "model_version": None, "error": error_message}


class Transcriber(Protocol):
    location: str

    async def check_status(self) -> dict: ...

    async def transcribe(self, samples: np.ndarray) -> str: ...

    async def close(self) -> None: ...


class LocalWhisperTranscriber:
    def __init__(self, model_path: Path, thread_count: int):
        # Imported here so the server still starts without pywhispercpp; browsers then use their own recognition.
        from pywhispercpp.model import Model

        logging.getLogger("pywhispercpp").setLevel(logging.WARNING)
        self.location = "in-process"
        self.model_version = f"whisper.cpp/{model_path.name}"
        self._model = Model(
            str(model_path),
            n_threads=thread_count,
            # Without this, whisper.cpp uses the previous utterance as a prompt and can echo the keyword.
            no_context=True,
            print_progress=False,
            print_realtime=False,
            redirect_whispercpp_logs_to=None,
        )
        self._model_lock = threading.Lock()

    async def check_status(self) -> dict:
        return {"url": self.location, "available": True, "model_version": self.model_version, "error": None}

    async def transcribe(self, samples: np.ndarray) -> str:
        normalized_audio = samples.astype(np.float32) / MAXIMUM_SAMPLE_MAGNITUDE
        return await asyncio.to_thread(self._transcribe_blocking, normalized_audio)

    def _transcribe_blocking(self, normalized_audio: np.ndarray) -> str:
        with self._model_lock:
            segments = self._model.transcribe(normalized_audio)
        return remove_non_speech_annotations(" ".join(segment.text for segment in segments))

    async def close(self) -> None:
        pass


class SpeechApiTranscriber:
    def __init__(self, speech_api_url: str):
        self.location = speech_api_url
        self._http_client = httpx.AsyncClient(timeout=SPEECH_API_REQUEST_TIMEOUT_SECONDS)

    async def check_status(self) -> dict:
        try:
            response = await self._http_client.get(f"{self.location}/health", timeout=SPEECH_API_HEALTH_TIMEOUT_SECONDS)
            response.raise_for_status()
            model_version = response.json().get("model_version")
        except (httpx.HTTPError, ValueError) as error:
            error_message = str(error) or type(error).__name__
            return {"url": self.location, "available": False, "model_version": None, "error": error_message}
        return {"url": self.location, "available": True, "model_version": model_version, "error": None}

    async def transcribe(self, samples: np.ndarray) -> str:
        # No Whisper prompt on purpose: on noisy audio Whisper tends to echo the prompt back.
        files = {"file": ("utterance.wav", samples_to_wav_bytes(samples), "audio/wav")}
        response = await self._http_client.post(f"{self.location}/transcribe", files=files)
        response.raise_for_status()
        return remove_non_speech_annotations(response.json()["text"])

    async def close(self) -> None:
        await self._http_client.aclose()
