import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator

DECIMAL_PATTERN = re.compile(r"^\d+(\.\d{1,2})?$")


def validate_nombre_str(v: Any) -> str:
    if not isinstance(v, str):
        raise ValueError("El nombre debe ser una cadena de texto.")
    v_stripped = v.strip()
    if len(v_stripped) == 0:
        raise ValueError("El nombre no puede estar vacío ni contener solo espacios.")
    if len(v_stripped) > 150:
        raise ValueError("El nombre no puede exceder 150 caracteres.")
    return v_stripped


def validate_descripcion_str(v: Any) -> str | None:
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("La descripción debe ser una cadena de texto o null.")
    if len(v) > 1000:
        raise ValueError("La descripción no puede exceder 1000 caracteres.")
    return v


def validate_precio_str(v: Any) -> str:
    if isinstance(v, bool):
        raise ValueError("El precio no puede ser un valor booleano.")
    if isinstance(v, (int, float, Decimal)):
        v_str = str(v)
    elif isinstance(v, str):
        v_str = v.strip()
    else:
        raise ValueError("El precio debe ser un número o una cadena decimal válida.")

    if "e" in v_str.lower():
        raise ValueError("No se permite notación científica en el precio.")
    if not DECIMAL_PATTERN.match(v_str):
        raise ValueError("El precio debe ser un número decimal válido con hasta dos decimales.")
    try:
        d = Decimal(v_str)
    except InvalidOperation:
        raise ValueError("El precio no es un valor decimal válido.")
    if d <= Decimal("0"):
        raise ValueError("El precio debe ser un valor estrictamente positivo mayor que cero.")
    if d > Decimal("99999999.99"):
        raise ValueError("El precio excede el valor máximo permitido (99999999.99).")
    return f"{d:.2f}"


def validate_activo_bool(v: Any) -> bool:
    if not isinstance(v, bool):
        raise ValueError("El campo 'activo' debe ser un valor booleano (true o false).")
    return v


class ProductoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    nombre: str
    descripcion: str | None = None
    precio: str | float | int
    activo: bool = True

    @field_validator("nombre", mode="before")
    @classmethod
    def check_nombre(cls, v: Any) -> str:
        return validate_nombre_str(v)

    @field_validator("descripcion", mode="before")
    @classmethod
    def check_descripcion(cls, v: Any) -> str | None:
        return validate_descripcion_str(v)

    @field_validator("precio", mode="before")
    @classmethod
    def check_precio(cls, v: Any) -> str:
        return validate_precio_str(v)

    @field_validator("activo", mode="before")
    @classmethod
    def check_activo(cls, v: Any) -> bool:
        return validate_activo_bool(v)


class ProductoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    nombre: str | None = None
    descripcion: str | None = None
    precio: str | float | int | None = None
    activo: bool | None = None

    @field_validator("nombre", mode="before")
    @classmethod
    def check_nombre(cls, v: Any) -> str:
        if v is None:
            raise ValueError("El campo 'nombre' no puede ser null.")
        return validate_nombre_str(v)

    @field_validator("descripcion", mode="before")
    @classmethod
    def check_descripcion(cls, v: Any) -> str | None:
        return validate_descripcion_str(v)

    @field_validator("precio", mode="before")
    @classmethod
    def check_precio(cls, v: Any) -> str:
        if v is None:
            raise ValueError("El campo 'precio' no puede ser null.")
        return validate_precio_str(v)

    @field_validator("activo", mode="before")
    @classmethod
    def check_activo(cls, v: Any) -> bool:
        if v is None:
            raise ValueError("El campo 'activo' no puede ser null.")
        return validate_activo_bool(v)

    @model_validator(mode="after")
    def check_non_empty(self) -> "ProductoUpdate":
        if not self.model_fields_set:
            raise ValueError("empty_patch")
        return self


class ProductoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | str
    nombre: str
    descripcion: str | None
    precio: Decimal | str
    activo: bool
    created_at: datetime | str
    updated_at: datetime | str

    @field_serializer("id")
    def serialize_id(self, v: Any) -> str:
        return str(v)

    @field_serializer("precio")
    def serialize_precio(self, v: Any) -> str:
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


class ProductoListResponse(BaseModel):
    items: list[ProductoResponse]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    loc: list[str]
    code: str
    msg: str


class ErrorResponse(BaseModel):
    detail: list[ErrorDetail]
