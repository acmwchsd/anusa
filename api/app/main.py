import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from . import model_downloads, websocket_messages
from .app_state import AppState
from .class_roster import ClassRoster
from .config import Config
from .errors import register_error_handlers
from .face_analysis import FaceAnalyzer
from .photo_store import PhotoStore
from .routes import live_stream, people, photos, system
from .settings import Settings
from .transcription import LocalWhisperTranscriber, SpeechApiTranscriber, Transcriber, unavailable_speech_status

logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(name)s: %(message)s")
logger = logging.getLogger("app")

SPEECH_STATUS_POLL_INTERVAL_SECONDS = 10


def create_app(config: Config | None = None) -> FastAPI:
    config = config or Config.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app_state = await asyncio.to_thread(load_app_state, config)
        app.state.app_state = app_state
        speech_status_watcher = asyncio.create_task(watch_speech_status(app_state))
        yield
        speech_status_watcher.cancel()
        if app_state.transcriber:
            await app_state.transcriber.close()

    app = FastAPI(title="Techpreneure Cam API", lifespan=lifespan)
    register_error_handlers(app)
    for route_module in (system, people, photos, live_stream):
        app.include_router(route_module.router)

    if config.web_build_directory:
        logger.info("serving the web app from %s", config.web_build_directory)
        app.mount("/", SinglePageAppFiles(directory=config.web_build_directory, html=True), name="web")
    else:
        logger.info("no web app in WEB_DIR: serving the API and /ws only")
    return app


def load_app_state(config: Config) -> AppState:
    cv2.setNumThreads(config.opencv_threads)
    config.data_directory.mkdir(parents=True, exist_ok=True)

    detector_model_path = model_downloads.ensure_model_file(config.models_directory, model_downloads.FACE_DETECTOR_MODEL)
    recognizer_model_path = model_downloads.ensure_model_file(
        config.models_directory, model_downloads.FACE_RECOGNIZER_MODEL
    )
    face_analyzer = FaceAnalyzer(detector_model_path, recognizer_model_path)
    logger.info("models loaded: %s + %s", detector_model_path.name, recognizer_model_path.name)

    roster = ClassRoster(config.data_directory)
    photo_store = PhotoStore(config.data_directory)
    logger.info(
        "%d people (%d reference photos), %d photos in %s",
        len(roster.list_people()),
        roster.count_reference_photos(),
        len(photo_store.list_newest_first()),
        config.data_directory,
    )

    transcriber, unavailable_reason = load_transcriber(config)
    return AppState(
        config=config,
        face_analyzer=face_analyzer,
        roster=roster,
        photo_store=photo_store,
        settings=Settings.load(config.data_directory),
        transcriber=transcriber,
        speech_status=unavailable_speech_status(unavailable_reason),
    )


def load_transcriber(config: Config) -> tuple[Transcriber | None, str | None]:
    if config.speech_engine == "http":
        return SpeechApiTranscriber(config.speech_api_url), None
    if config.speech_engine == "off":
        logger.info("SPEECH=off: the voice trigger runs in the browser only")
        return None, None
    try:
        model_path = model_downloads.ensure_whisper_model_file(config.models_directory, config.whisper_model_filename)
        transcriber = LocalWhisperTranscriber(model_path, config.whisper_threads)
    except Exception as error:
        unavailable_reason = f"whisper.cpp not loaded: {error}"
        logger.warning("%s (browsers fall back to their own speech recognition)", unavailable_reason)
        return None, unavailable_reason
    logger.info("whisper.cpp loaded: %s, %d threads", model_path.name, config.whisper_threads)
    return transcriber, None


async def watch_speech_status(app_state: AppState) -> None:
    if app_state.transcriber is None:
        return
    was_available = None
    while True:
        speech_status = await app_state.transcriber.check_status()
        app_state.speech_status = speech_status
        if speech_status["available"] != was_available:
            if speech_status["available"]:
                logger.info("Whisper ready: %s (%s)", app_state.transcriber.location, speech_status["model_version"])
            else:
                logger.warning(
                    "Whisper unreachable at %s: browsers fall back to their own speech recognition",
                    app_state.transcriber.location,
                )
            was_available = speech_status["available"]
            app_state.broadcast(websocket_messages.speech_status_changed(speech_status))
        await asyncio.sleep(SPEECH_STATUS_POLL_INTERVAL_SECONDS)


class SinglePageAppFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            is_api_path = Path(path).parts[:1] == ("api",)
            if error.status_code != 404 or is_api_path:
                raise
            return await super().get_response("index.html", scope)


app = create_app()
