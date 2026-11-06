import hashlib
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ModelFile:
    filename: str
    download_url: str
    sha256_checksum: str


FACE_DETECTOR_MODEL = ModelFile(
    filename="face_detection_yunet_2023mar.onnx",
    download_url="https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    sha256_checksum="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)

FACE_RECOGNIZER_MODEL = ModelFile(
    filename="face_recognition_sface_2021dec.onnx",
    download_url="https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
    sha256_checksum="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
)

WHISPER_BASE_ENGLISH_MODEL = ModelFile(
    filename="ggml-base.en.bin",
    download_url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
    sha256_checksum="a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002",
)

DOWNLOADABLE_WHISPER_MODELS = {model.filename: model for model in (WHISPER_BASE_ENGLISH_MODEL,)}


def ensure_model_file(models_directory: Path, model: ModelFile) -> Path:
    model_path = models_directory / model.filename
    if model_path.exists():
        verify_checksum(model_path.read_bytes(), model, f"{model_path} (delete it to download it again)")
        return model_path

    logger.info("downloading %s", model.download_url)
    models_directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(model.download_url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        downloaded_bytes = response.read()
    verify_checksum(downloaded_bytes, model, "the downloaded file")

    partial_download_path = model_path.with_suffix(".part")
    partial_download_path.write_bytes(downloaded_bytes)
    partial_download_path.replace(model_path)
    return model_path


def ensure_whisper_model_file(models_directory: Path, filename: str) -> Path:
    if filename in DOWNLOADABLE_WHISPER_MODELS:
        return ensure_model_file(models_directory, DOWNLOADABLE_WHISPER_MODELS[filename])
    model_path = models_directory / filename
    if not model_path.exists():
        downloadable_filenames = ", ".join(DOWNLOADABLE_WHISPER_MODELS)
        raise FileNotFoundError(f"{model_path} not found (only {downloadable_filenames} is downloaded automatically)")
    return model_path


def verify_checksum(file_bytes: bytes, model: ModelFile, file_description: str) -> None:
    actual_checksum = hashlib.sha256(file_bytes).hexdigest()
    if actual_checksum != model.sha256_checksum:
        raise RuntimeError(f"{file_description} has sha256 {actual_checksum}, expected {model.sha256_checksum}")
