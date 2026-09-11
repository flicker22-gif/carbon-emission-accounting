from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

DEFAULT_REGION = "全国"


class Facility(Base):
    """厂区/核算边界内的设施"""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(50), default=DEFAULT_REGION)  # 省份,用于匹配地区因子
    location: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    records: Mapped[list["EnergyRecord"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )


class EmissionFactor(Base):
    """排放因子：按 能源类型 + 地区 + 适用年度 版本化维护。

    factor_value 单位为 kgCO2e / unit。同一 (energy_type, region, year) 唯一。
    region = "全国" 表示全国通用兜底因子。
    """

    __tablename__ = "emission_factors"
    __table_args__ = (
        UniqueConstraint("energy_type", "region", "year", name="uq_factor_type_region_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 / 2 / 3
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    factor_value: Mapped[float] = mapped_column(Float, nullable=False)  # kgCO2e / unit
    region: Mapped[str] = mapped_column(String(50), default=DEFAULT_REGION, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)  # 适用年度
    source: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)


class EnergyRecord(Base):
    """能耗活动数据录入记录。

    只存能源类型,不绑定具体因子;计算排放量时按厂区地区 + 数据期间
    动态匹配最新适用因子,因子库更新后历史数据自动按新因子重算。
    """

    __tablename__ = "energy_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    consumption: Mapped[float] = mapped_column(Float, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    facility: Mapped[Facility] = relationship(back_populates="records")
