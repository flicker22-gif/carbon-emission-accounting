from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Facility(Base):
    """厂区/核算边界内的设施"""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    records: Mapped[list["EnergyRecord"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class EmissionFactor(Base):
    """排放因子：单位活动数据对应的 kgCO2e 排放量"""

    __tablename__ = "emission_factors"

    id: Mapped[int] = mapped_column(primary_key=True)
    energy_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 / 2 / 3
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # 如 固定燃烧 / 外购电力
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # 活动数据单位，如 m³、kWh
    factor_value: Mapped[float] = mapped_column(Float, nullable=False)  # kgCO2e / unit
    source: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)

    records: Mapped[list["EnergyRecord"]] = relationship(back_populates="factor")


class EnergyRecord(Base):
    """能耗活动数据录入记录"""

    __tablename__ = "energy_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    factor_id: Mapped[int] = mapped_column(ForeignKey("emission_factors.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    consumption: Mapped[float] = mapped_column(Float, nullable=False)  # 消耗量（因子对应单位）
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    facility: Mapped[Facility] = relationship(back_populates="records")
    factor: Mapped[EmissionFactor] = relationship(back_populates="records")

    @property
    def emissions_tco2e(self) -> float:
        """排放量（tCO2e）= 活动数据 × 因子(kgCO2e) / 1000"""
        return self.consumption * self.factor.factor_value / 1000.0
