"""Starts the server: python -m app"""

import uvicorn

from .config import Config

config = Config.from_environment()
uvicorn.run("app.main:app", host=config.host, port=config.port)
