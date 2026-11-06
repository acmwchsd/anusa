import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    @classmethod
    def bad_request(cls, message: str) -> "ApiError":
        return cls(400, message)

    @classmethod
    def not_found(cls, resource_name: str) -> "ApiError":
        return cls(404, f"{resource_name} not found")

    @classmethod
    def conflict(cls, message: str) -> "ApiError":
        return cls(409, message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse({"error": error.message}, status_code=error.status_code)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse({"error": str(error.detail)}, status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        first_problem = error.errors()[0]
        field_path = ".".join(str(part) for part in first_problem["loc"])
        return JSONResponse({"error": f"{field_path}: {first_problem['msg']}"}, status_code=422)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception("%s %s failed", request.method, request.url.path)
        return JSONResponse({"error": str(error) or type(error).__name__}, status_code=500)
