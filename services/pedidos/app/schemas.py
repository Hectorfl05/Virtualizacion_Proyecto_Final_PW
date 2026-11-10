import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator


def validate_cantidad_int(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError("La cantidad debe ser un número entero.")
    if v <= 0:
        raise ValueError("La cantidad debe ser un entero estrictamente mayor que cero.")
    return v


def validate_producto_id(v: Any) -> uuid.UUID:
    if isinstance(v, uuid.UUID):
        return v
    if isinstance(v, str):
        try:
            return uuid.UUID(v)
        except ValueError:
            raise ValueError("Identificador UUID inválido.")
    raise ValueError("Identificador UUID inválido.")


class PedidoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    producto_id: uuid.UUID
    cantidad: int

    @field_validator("producto_id", mode="before")
    @classmethod
    def check_producto_id(cls, v: Any) -> uuid.UUID:
        return validate_producto_id(v)

    @field_validator("cantidad", mode="before")
    @classmethod
    def check_cantidad(cls, v: Any) -> int:
        return validate_cantidad_int(v)


class PedidoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    producto_id: uuid.UUID | None = None
    cantidad: int | None = None

    @field_validator("producto_id", mode="before")
    @classmethod
    def check_producto_id(cls, v: Any) -> uuid.UUID:
        if v is None:
            raise ValueError("El campo 'producto_id' no puede ser null.")
        return validate_producto_id(v)

    @field_validator("cantidad", mode="before")
    @classmethod
    def check_cantidad(cls, v: Any) -> int:
        if v is None:
            raise ValueError("El campo 'cantidad' no puede ser null.")
        return validate_cantidad_int(v)

    @model_validator(mode="after")
    def check_non_empty(self) -> "PedidoUpdate":
        if not self.model_fields_set:
            raise ValueError("empty_patch")
        return self


class PedidoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    producto_id: uuid.UUID | str
    producto_nombre: str
    cantidad: int
    precio_unitario: Decimal | str
    total: Decimal | str
    created_at: datetime | str
    updated_at: datetime | str

    @field_serializer("id", "producto_id")
    def serialize_uuid(self, v: Any) -> str:
        return str(v)

    @field_serializer("precio_unitario", "total")
    def serialize_decimal(self, v: Any) -> str:
        if isinstance(v, (Decimal, int, float)):
            return f"{Decimal(str(v)):.2f}"
        return f"{Decimal(v):.2f}"

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, v: Any) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=UTC)
            else:
                v = v.astimezone(UTC)
            iso = v.isoformat()
            if iso.endswith("+00:00"):
                return iso[:-6] + "Z"
            if not iso.endswith("Z"):
                return iso + "Z"
            return iso
        return str(v)


class PedidoListResponse(BaseModel):
    items: list[PedidoResponse]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    loc: list[str]
    code: str
    msg: str


class ErrorResponse(BaseModel):
    detail: list[ErrorDetail]
