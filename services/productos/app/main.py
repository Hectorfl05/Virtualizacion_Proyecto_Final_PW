import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.database import build_engine

logger = logging.getLogger("panaderia.productos")


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"


class ErrorDetail(BaseModel):
    loc: list[str]
    code: str
    msg: str


class ErrorResponse(BaseModel):
    detail: list[ErrorDetail]


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings if settings is not None else get_settings()
        logging.basicConfig(
            level=config.log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        engine = build_engine(config)
        app.state.engine = engine
        app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        logger.info("Servicio productos iniciado")
        try:
            yield
        finally:
            engine.dispose()
            logger.info("Servicio productos detenido")

    app = FastAPI(title="Panadería - Productos", version="0.1.0", lifespan=lifespan)

    @app.get("/health/live", response_model=LiveResponse, tags=["salud"])
    def live() -> LiveResponse:
        return LiveResponse()

    @app.get(
        "/health/ready",
        response_model=ReadyResponse,
        responses={503: {"model": ErrorResponse, "description": "Base propia inaccesible"}},
        tags=["salud"],
    )
    def ready(request: Request):
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("Base propia no disponible para readiness")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": [
                        {
                            "loc": ["server"],
                            "code": "database_unavailable",
                            "msg": "Base de datos no disponible.",
                        }
                    ]
                },
            )
        return ReadyResponse()

    return app


app = create_app()
