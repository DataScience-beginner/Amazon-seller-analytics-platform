import base64
import binascii
import logging
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApplicationError

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware:
    """Attach a request identifier without BaseHTTPMiddleware stream buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        async def send_with_correlation_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_correlation_id)


class PreviewBasicAuthMiddleware:
    """Protect the temporary hosted preview until tenant authentication exists."""

    def __init__(self, app: ASGIApp, *, username: str, password: str) -> None:
        self.app = app
        self.username = username
        self.password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/api/v1/health":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        supplied_username, supplied_password = _basic_credentials(authorization)
        if not (
            secrets.compare_digest(supplied_username, self.username)
            and secrets.compare_digest(supplied_password, self.password)
        ):
            response = JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "preview_authentication_required",
                        "message": "SellerOS preview authentication is required",
                    }
                },
                headers={"WWW-Authenticate": 'Basic realm="SellerOS Preview"'},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _basic_credentials(authorization: str) -> tuple[str, str]:
    scheme, _, encoded = authorization.partition(" ")
    if scheme.casefold() != "basic" or not encoded:
        return "", ""
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return "", ""
    username, separator, password = decoded.partition(":")
    return (username, password) if separator else ("", "")


def _correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None)
    return str(correlation_id or uuid.uuid4())


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
) -> JSONResponse:
    correlation_id = _correlation_id(request)
    content: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        }
    }
    if details:
        error = content["error"]
        if isinstance(error, dict):
            error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"X-Correlation-ID": correlation_id},
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.upload_directory.mkdir(parents=True, exist_ok=True)
    logger.info("SellerOS application started", extra={"environment": settings.environment})
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    if settings.preview_basic_auth_username and settings.preview_basic_auth_password:
        app.add_middleware(
            PreviewBasicAuthMiddleware,
            username=settings.preview_basic_auth_username,
            password=settings.preview_basic_auth_password,
        )
    app.include_router(api_router)

    @app.exception_handler(ApplicationError)
    async def application_exception_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "code": error["type"],
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return _error_response(
            request,
            status_code=422,
            code="validation_error",
            message="The request could not be validated",
            details={"fields": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = (
            exc.detail if isinstance(exc.detail, str) else "The request could not be completed"
        )
        return _error_response(
            request,
            status_code=exc.status_code,
            code="http_error",
            message=message,
        )

    @app.exception_handler(Exception)
    async def safe_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = _correlation_id(request)
        logger.exception(
            "Unhandled request failure",
            exc_info=exc,
            extra={"correlation_id": correlation_id},
        )
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="Internal server error",
        )

    _mount_frontend(app, settings.frontend_dist_directory)
    return app


def _mount_frontend(app: FastAPI, frontend_directory: Path | None) -> None:
    """Serve built same-origin assets after API/docs routes when a build is configured."""
    if frontend_directory is None:
        return
    root = frontend_directory.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST_DIRECTORY does not contain an index.html: {root}")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend(frontend_path: str) -> FileResponse:
        if frontend_path == "api" or frontend_path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        candidate = (root / frontend_path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
