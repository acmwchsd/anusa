import os
from dataclasses import dataclass
from pathlib import Path

SPEECH_ENGINES = ("local", "http", "off")


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    models_directory: Path
    data_directory: Path
    web_build_directory: Path | None
    speech_api_url: str | None
    opencv_threads: int
    speech_engine: str = "off"
    whisper_model_filename: str = "ggml-base.en.bin"
    whisper_threads: int = 4

    @classmethod
    def from_environment(cls) -> "Config":
        bind_address = os.getenv("BIND", "0.0.0.0:8004")
        host, _, port = bind_address.rpartition(":")
        if not host or not port.isdigit():
            raise ValueError(f"BIND must look like 0.0.0.0:8004, got {bind_address!r}")

        speech_api_url = os.getenv("SPEECH_URL", "").strip().rstrip("/") or None
        speech_engine = os.getenv("SPEECH", "").strip().lower() or ("http" if speech_api_url else "local")
        if speech_engine not in SPEECH_ENGINES:
            raise ValueError(f"SPEECH must be one of {', '.join(SPEECH_ENGINES)}, got {speech_engine!r}")
        if speech_engine == "http" and not speech_api_url:
            raise ValueError("SPEECH=http needs SPEECH_URL, like http://localhost:8002")

        web_build_directory = Path(os.getenv("WEB_DIR", "../web/build"))
        return cls(
            host=host,
            port=int(port),
            models_directory=Path(os.getenv("MODEL_DIR", "../models")),
            data_directory=Path(os.getenv("DATA_DIR", "./data")),
            web_build_directory=web_build_directory if (web_build_directory / "index.html").exists() else None,
            speech_api_url=speech_api_url,
            opencv_threads=int(os.getenv("THREADS", "4")),
            speech_engine=speech_engine,
            whisper_model_filename=os.getenv("WHISPER_MODEL", "ggml-base.en.bin"),
            whisper_threads=int(os.getenv("WHISPER_THREADS", "4")),
        )
