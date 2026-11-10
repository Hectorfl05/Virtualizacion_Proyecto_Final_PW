import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.clients.productos import (
    ProductInactiveError,
    ProductNotFoundError,
    ProductosClient,
    ProductsUnavailableError,
)
from app.config import Settings, get_settings
from app.database import build_engine
from app.routes import router as pedidos_router
from app.service import PedidoNotFoundError, PedidoService

logger = logging.getLogger("panaderia.pedidos")


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
        app.state.productos_client = ProductosClient(
            base_url=config.productos_base_url,
            timeout_seconds=config.productos_timeout_seconds,
        )
        app.state.pedido_service = PedidoService(productos_client=app.state.productos_client)
        logger.info("Servicio pedidos iniciado")
        try:
            yield
        finally:
            engine.dispose()
            logger.info("Servicio pedidos detenido")

    app = FastAPI(title="Panadería - Pedidos", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = [str(x) for x in err.get("loc", ())]
            err_type = str(err.get("type", ""))
            raw_msg = str(err.get("msg", ""))

            if err_type == "extra_forbidden":
                code = "extra_field"
                field_name = loc[-1] if loc else "desconocido"
                msg = f"El campo '{field_name}' no está permitido."
            elif "empty_patch" in raw_msg or "empty_patch" in err_type:
                code = "empty_patch"
                loc = ["body"]
                msg = "El cuerpo de actualización no puede estar vacío."
            elif err_type == "json_invalid":
                code = "invalid_value"
                loc = ["body"]
                msg = "JSON malformado o inválido."
            elif loc == ["body"] and err_type in (
                "model_type",
                "dict_type",
                "model_attributes_type",
            ):
                code = "invalid_value"
                msg = "El cuerpo debe ser un objeto JSON."
            elif loc == ["path", "id"]:
                code = "invalid_value"
                msg = "Identificador UUID inválido."
            elif loc == ["query", "limit"]:
                code = "invalid_value"
                msg = "El parámetro 'limit' debe ser un entero entre 1 y 100."
            elif loc == ["query", "offset"]:
                code = "invalid_value"
                msg = "El parámetro 'offset' debe ser un entero mayor o igual a 0."
            else:
                code = "invalid_value"
                if raw_msg.startswith("Value error, "):
                    msg = raw_msg[len("Value error, ") :].strip()
                elif raw_msg.startswith("Field required"):
                    field = loc[-1] if loc else "campo"
                    msg = f"El campo '{field}' es obligatorio."
                else:
                    msg = raw_msg
            details.append({"loc": loc, "code": code, "msg": msg})
        return JSONResponse(status_code=422, content={"detail": details})

    @app.exception_handler(ProductNotFoundError)
    async def product_not_found_handler(request: Request, exc: ProductNotFoundError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": ["body", "producto_id"],
                        "code": "product_not_found",
                        "msg": "El producto especificado no existe.",
                    }
                ]
            },
        )

    @app.exception_handler(ProductInactiveError)
    async def product_inactive_handler(request: Request, exc: ProductInactiveError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": ["body", "producto_id"],
                        "code": "product_inactive",
                        "msg": "El producto especificado no está activo para nuevos pedidos.",
                    }
                ]
            },
        )

    @app.exception_handler(ProductsUnavailableError)
    async def products_unavailable_handler(request: Request, exc: ProductsUnavailableError):
        logger.warning("Fallo operativo al consultar servicio de productos: %s", str(exc))
        return JSONResponse(
            status_code=503,
            content={
                "detail": [
                    {
                        "loc": ["server"],
                        "code": "products_unavailable",
                        "msg": "El servicio de productos no está disponible temporalmente.",
                    }
                ]
            },
        )

    @app.exception_handler(PedidoNotFoundError)
    async def pedido_not_found_handler(request: Request, exc: PedidoNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "detail": [
                    {
                        "loc": ["path", "id"],
                        "code": "not_found",
                        "msg": "Pedido no encontrado.",
                    }
                ]
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error("Error en base de datos: %s", exc.__class__.__name__)
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

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": [
                        {
                            "loc": ["path"],
                            "code": "not_found",
                            "msg": "Recurso no encontrado.",
                        }
                    ]
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": [
                    {
                        "loc": ["server"],
                        "code": "internal_error",
                        "msg": str(exc.detail) if isinstance(exc.detail, str) else "Error HTTP.",
                    }
                ]
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Error inesperado en el servidor")
        return JSONResponse(
            status_code=500,
            content={
                "detail": [
                    {
                        "loc": ["server"],
                        "code": "internal_error",
                        "msg": "Error interno del servidor.",
                    }
                ]
            },
        )

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

    app.include_router(pedidos_router)

    return app


app = create_app()
