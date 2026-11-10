import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas import (
    ErrorResponse,
    PedidoCreate,
    PedidoListResponse,
    PedidoResponse,
    PedidoUpdate,
)
from app.service import PedidoService

router = APIRouter(
    prefix="/pedidos",
    tags=["pedidos"],
    responses={
        422: {"model": ErrorResponse, "description": "Entrada inválida o error de validación"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"},
        503: {"model": ErrorResponse, "description": "Servicio o base de datos no disponible"},
    },
)


def get_pedido_service(request: Request) -> PedidoService:
    service: PedidoService | None = getattr(request.app.state, "pedido_service", None)
    if service is not None:
        return service
    return PedidoService()


@router.post(
    "",
    response_model=PedidoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear pedido",
)
def create_pedido(
    payload: PedidoCreate,
    db: Session = Depends(get_session),
    service: PedidoService = Depends(get_pedido_service),
) -> PedidoResponse:
    pedido = service.create_pedido(db, payload)
    return PedidoResponse.model_validate(pedido)


@router.get(
    "",
    response_model=PedidoListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar pedidos paginados (filtro opcional por producto_id)",
)
def list_pedidos(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    producto_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_session),
    service: PedidoService = Depends(get_pedido_service),
) -> PedidoListResponse:
    items, total = service.list_pedidos(db, limit, offset, producto_id)
    return PedidoListResponse(
        items=[PedidoResponse.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{id}",
    response_model=PedidoResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse, "description": "Pedido no encontrado"}},
    summary="Consultar pedido por id",
)
def get_pedido(
    id: uuid.UUID,
    db: Session = Depends(get_session),
    service: PedidoService = Depends(get_pedido_service),
) -> PedidoResponse:
    pedido = service.get_pedido(db, id)
    return PedidoResponse.model_validate(pedido)


@router.patch(
    "/{id}",
    response_model=PedidoResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse, "description": "Pedido no encontrado"}},
    summary="Actualizar parcialmente pedido",
)
def update_pedido(
    id: uuid.UUID,
    payload: PedidoUpdate,
    db: Session = Depends(get_session),
    service: PedidoService = Depends(get_pedido_service),
) -> PedidoResponse:
    pedido = service.update_pedido(db, id, payload)
    return PedidoResponse.model_validate(pedido)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse, "description": "Pedido no encontrado"}},
    summary="Eliminar pedido físicamente",
)
def delete_pedido(
    id: uuid.UUID,
    db: Session = Depends(get_session),
    service: PedidoService = Depends(get_pedido_service),
) -> Response:
    service.delete_pedido(db, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
