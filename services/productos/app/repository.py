import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Producto


class ProductoRepository:
    def get_by_id(self, session: Session, producto_id: uuid.UUID) -> Producto | None:
        return session.get(Producto, producto_id)

    def list_paginated(
        self, session: Session, limit: int, offset: int
    ) -> tuple[list[Producto], int]:
        total = session.scalar(select(func.count()).select_from(Producto)) or 0
        items = list(
            session.scalars(
                select(Producto)
                .order_by(Producto.created_at.asc(), Producto.id.asc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def create(self, session: Session, producto: Producto) -> Producto:
        session.add(producto)
        session.commit()
        session.refresh(producto)
        return producto

    def update(self, session: Session, producto: Producto) -> Producto:
        session.commit()
        session.refresh(producto)
        return producto

    def delete(self, session: Session, producto: Producto) -> None:
        session.delete(producto)
        session.commit()
