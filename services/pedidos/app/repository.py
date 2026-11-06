import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Pedido


class PedidoRepository:
    def get_by_id(self, session: Session, pedido_id: uuid.UUID) -> Pedido | None:
        return session.get(Pedido, pedido_id)

    def list_paginated(self, session: Session, limit: int, offset: int) -> tuple[list[Pedido], int]:
        total = session.scalar(select(func.count()).select_from(Pedido)) or 0
        items = list(
            session.scalars(
                select(Pedido)
                .order_by(Pedido.created_at.asc(), Pedido.id.asc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def create(self, session: Session, pedido: Pedido) -> Pedido:
        session.add(pedido)
        session.commit()
        session.refresh(pedido)
        return pedido

    def update(self, session: Session, pedido: Pedido) -> Pedido:
        session.commit()
        session.refresh(pedido)
        return pedido

    def delete(self, session: Session, pedido: Pedido) -> None:
        session.delete(pedido)
        session.commit()
