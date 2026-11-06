import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Producto
from app.repository import ProductoRepository
from app.schemas import ProductoCreate, ProductoUpdate


class ProductNotFoundError(Exception):
    def __init__(self, producto_id: uuid.UUID):
        self.producto_id = producto_id
        super().__init__(f"Producto con id {producto_id} no encontrado.")


class ProductoService:
    def __init__(self, repository: ProductoRepository | None = None):
        self.repository = repository or ProductoRepository()

    def get_producto(self, session: Session, producto_id: uuid.UUID) -> Producto:
        producto = self.repository.get_by_id(session, producto_id)
        if producto is None:
            raise ProductNotFoundError(producto_id)
        return producto

    def list_productos(
        self, session: Session, limit: int, offset: int
    ) -> tuple[list[Producto], int]:
        return self.repository.list_paginated(session, limit, offset)

    def create_producto(self, session: Session, data: ProductoCreate) -> Producto:
        now = datetime.now(UTC)
        producto = Producto(
            id=uuid.uuid4(),
            nombre=data.nombre,
            descripcion=data.descripcion,
            precio=Decimal(data.precio),
            activo=data.activo,
            created_at=now,
            updated_at=now,
        )
        return self.repository.create(session, producto)

    def update_producto(
        self, session: Session, producto_id: uuid.UUID, data: ProductoUpdate
    ) -> Producto:
        producto = self.get_producto(session, producto_id)

        fields_set = data.model_fields_set
        if "nombre" in fields_set and data.nombre is not None:
            producto.nombre = data.nombre
        if "descripcion" in fields_set:
            producto.descripcion = data.descripcion
        if "precio" in fields_set and data.precio is not None:
            producto.precio = Decimal(data.precio)
        if "activo" in fields_set and data.activo is not None:
            producto.activo = data.activo

        producto.updated_at = datetime.now(UTC)
        return self.repository.update(session, producto)

    def delete_producto(self, session: Session, producto_id: uuid.UUID) -> None:
        producto = self.get_producto(session, producto_id)
        self.repository.delete(session, producto)
