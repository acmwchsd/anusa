from pathlib import Path
from pydantic import BaseModel
from .json_files import read_json_file, write_json_file_atomically

SETTINGS_FILENAME = "settings.json"
DEFAULT_KEYWORDS = ["techpreneure"]

class Settings(BaseModel):
    match_threshold: float = 0.45
    keywords: list[str] = DEFAULT_KEYWORDS
    keyword_sensitivity: float = 0.75
    cooldown_s: float = 3.0

    @classmethod
    def load(cls, data_directory: Path) -> "Settings":
        saved_settings = read_json_file(data_directory / SETTINGS_FILENAME, {})
        return cls.model_validate(saved_settings).sanitized()

    def save(self, data_directory: Path) -> None:
        write_json_file_atomically(data_directory / SETTINGS_FILENAME, self.model_dump())

    def sanitized(self) -> "Settings":
        """Clamps every value into a sensible range and drops empty keywords."""
        non_empty_keywords = [keyword.strip() for keyword in self.keywords if keyword.strip()]
        return Settings(
            match_threshold=clamp(self.match_threshold, 0.2, 0.95),
            keywords=non_empty_keywords or DEFAULT_KEYWORDS,
            keyword_sensitivity=clamp(self.keyword_sensitivity, 0.5, 1.0),
            cooldown_s=clamp(self.cooldown_s, 0.0, 60.0),
        )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
