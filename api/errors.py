from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.middleware.request_id import REQUEST_ID_HEADER
from api.schemas.error import ErrorBody, ErrorResponse
from core.services.video_service import (
    VideoNotFoundError,
    VideoUploadConflictError,
    VideoUploadStorageError,
)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    request_id = _request_id(request)
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers={REQUEST_ID_HEADER: request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VideoNotFoundError)
    async def video_not_found_handler(
        request: Request,
        exc: VideoNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=404,
            code="video_not_found",
            message=str(exc),
        )

    @app.exception_handler(VideoUploadConflictError)
    async def video_upload_conflict_handler(
        request: Request,
        exc: VideoUploadConflictError,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=409,
            code="upload_not_active",
            message=str(exc),
        )

    @app.exception_handler(VideoUploadStorageError)
    async def video_upload_storage_handler(
        request: Request,
        _exc: VideoUploadStorageError,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=502,
            code="storage_unavailable",
            message="Storage unavailable",
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=exc.status_code,
            code=f"http_{exc.status_code}",
            message=str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=422,
            code="validation_error",
            message="Request validation failed",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        _exc: Exception,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=500,
            code="internal_error",
            message="Internal server error",
        )
