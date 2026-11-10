import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas import (
    ErrorResponse,
    ProductoCreate,
    ProductoListResponse,
    ProductoResponse,
    ProductoUpdate,
)
from app.service import ProductoService

router = APIRouter(
    prefix="/productos",
    tags=["productos"],
    responses={
        422: {"model": ErrorResponse, "description": "Entrada inválida o error de validación"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"},
        503: {"model": ErrorResponse, "description": "Base de datos no disponible"},
    },
)

service = ProductoService()


@router.post(
    "",
    response_model=ProductoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto",
)
def create_producto(
    payload: ProductoCreate, db: Session = Depends(get_session)
) -> ProductoResponse:
    producto = service.create_producto(db, payload)
    return ProductoResponse.model_validate(producto)


@router.get(
    "",
    response_model=ProductoListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar productos paginados",
)
def list_productos(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> ProductoListResponse:
    items, total = service.list_productos(db, limit, offset)
    return ProductoListResponse(
        items=[ProductoResponse.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{id}",
    response_model=ProductoResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse, "description": "Producto no encontrado"}},
    summary="Consultar producto por id",
)
def get_producto(id: uuid.UUID, db: Session = Depends(get_session)) -> ProductoResponse:
    producto = service.get_producto(db, id)
    return ProductoResponse.model_validate(producto)


@router.patch(
    "/{id}",
    response_model=ProductoResponse,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorResponse, "description": "Producto no encontrado"}},
    summary="Actualizar parcialmente producto",
)
def update_producto(
    id: uuid.UUID, payload: ProductoUpdate, db: Session = Depends(get_session)
) -> ProductoResponse:
    producto = service.update_producto(db, id, payload)
    return ProductoResponse.model_validate(producto)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse, "description": "Producto no encontrado"}},
    summary="Eliminar producto físicamente",
)
def delete_producto(id: uuid.UUID, db: Session = Depends(get_session)) -> Response:
    service.delete_producto(db, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
