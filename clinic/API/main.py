import logging
import time
from uuid import UUID, uuid4

import pyodbc
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from API.router import api_router
from Core.config import get_settings
from Core.errors import AppError
from Core.logging import configure_logging

configure_logging()
logger = logging.getLogger("clinic.api")
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API quản lý phòng khám dùng FastAPI, pyodbc và SQL Server.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


def error_body(request: Request, code: str, message: str, details: object = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": str(request.state.request_id),
        }
    }


@app.middleware("http")
async def request_context(request: Request, call_next):
    raw_request_id = request.headers.get("x-request-id")
    try:
        request_id = UUID(raw_request_id) if raw_request_id else uuid4()
    except ValueError:
        request_id = uuid4()
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = str(request_id)
    logger.info(
        "request_completed",
        extra={
            "request_id": str(request_id),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, exc.code, exc.message, exc.details),
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(item) for item in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body(request, "VALIDATION_ERROR", "Dữ liệu đầu vào không hợp lệ.", details),
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, "HTTP_ERROR", str(exc.detail)),
        headers=exc.headers,
    )


@app.exception_handler(pyodbc.Error)
async def database_error_handler(request: Request, exc: pyodbc.Error) -> JSONResponse:
    logger.exception(
        "database_error", extra={"request_id": str(request.state.request_id)}, exc_info=exc
    )
    return JSONResponse(
        status_code=503,
        content=error_body(
            request,
            "DATABASE_UNAVAILABLE",
            "Không thể xử lý yêu cầu với cơ sở dữ liệu lúc này.",
        ),
    )


app.include_router(api_router)
