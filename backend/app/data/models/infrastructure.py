"""Modelos de infraestructura física: ubicaciones, atrapanieblas, tanques e invernaderos."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.database import Base, TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    altitude_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FogCollector(Base, TimestampMixin):
    __tablename__ = "fog_collectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    mesh_area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    mesh_type: Mapped[str | None] = mapped_column(String(80))
    # Hacia dónde mira la malla (p. ej. «NE»): la captación depende del viento dominante.
    orientation: Mapped[str | None] = mapped_column(String(40))
    installed_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    location: Mapped[Location | None] = relationship(lazy="joined")


class Tank(Base, TimestampMixin):
    __tablename__ = "tanks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    fog_collector_id: Mapped[int | None] = mapped_column(ForeignKey("fog_collectors.id"))
    capacity_liters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Greenhouse(Base, TimestampMixin):
    __tablename__ = "greenhouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    tank_id: Mapped[int | None] = mapped_column(ForeignKey("tanks.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
