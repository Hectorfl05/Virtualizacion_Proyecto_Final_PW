import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.clients.productos import ProductosClient
from app.models import Pedido
from app.repository import PedidoRepository
from app.schemas import PedidoCreate, PedidoUpdate


class PedidoNotFoundError(Exception):
    def __init__(self, pedido_id: uuid.UUID):
        self.pedido_id = pedido_id
        super().__init__(f"Pedido con id {pedido_id} no encontrado.")


class PedidoService:
    def __init__(
        self,
        repository: PedidoRepository | None = None,
        productos_client: ProductosClient | None = None,
    ):
        self.repository = repository or PedidoRepository()
        self.productos_client = productos_client or ProductosClient()

    def create_pedido(self, session: Session, data: PedidoCreate) -> Pedido:
        remote_prod = self.productos_client.get_producto(data.producto_id)
        now = datetime.now(UTC)
        total = Decimal(data.cantidad) * remote_prod.precio
        pedido = Pedido(
            id=uuid.uuid4(),
            producto_id=data.producto_id,
            producto_nombre=remote_prod.nombre,
            cantidad=data.cantidad,
            precio_unitario=remote_prod.precio,
            total=total,
            created_at=now,
            updated_at=now,
        )
        return self.repository.create(session, pedido)

    def get_pedido(self, session: Session, pedido_id: uuid.UUID) -> Pedido:
        pedido = self.repository.get_by_id(session, pedido_id)
        if pedido is None:
            raise PedidoNotFoundError(pedido_id)
        return pedido

    def list_pedidos(
        self,
        session: Session,
        limit: int,
        offset: int,
        producto_id: uuid.UUID | None = None,
    ) -> tuple[list[Pedido], int]:
        return self.repository.list_paginated(session, limit, offset, producto_id)

    def update_pedido(self, session: Session, pedido_id: uuid.UUID, data: PedidoUpdate) -> Pedido:
        pedido = self.get_pedido(session, pedido_id)
        fields_set = data.model_fields_set

        # Si cambia el producto_id a uno distinto, se valida y toman datos actuales
        if "producto_id" in fields_set and data.producto_id is not None:
            if data.producto_id != pedido.producto_id:
                remote_prod = self.productos_client.get_producto(data.producto_id)
                pedido.producto_id = data.producto_id
                pedido.producto_nombre = remote_prod.nombre
                pedido.precio_unitario = remote_prod.precio

        # Si cambia la cantidad, se toma la nueva; de lo contrario se conserva la anterior
        if "cantidad" in fields_set and data.cantidad is not None:
            pedido.cantidad = data.cantidad

        # Recalcular el total con el precio_unitario (histórico o nuevo) y la cantidad resultante
        pedido.total = Decimal(pedido.cantidad) * pedido.precio_unitario
        pedido.updated_at = datetime.now(UTC)
        return self.repository.update(session, pedido)

    def delete_pedido(self, session: Session, pedido_id: uuid.UUID) -> None:
        pedido = self.get_pedido(session, pedido_id)
        self.repository.delete(session, pedido)
