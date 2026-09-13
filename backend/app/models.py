from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

DEFAULT_REGION = "全国"

# 导入批次状态机:
#   pending   已上传,合法行待复核(未计入任何汇总)
#   confirmed 复核通过,整批锁定,行记录写入 energy_records 并计入仪表盘/CSV
#   rejected  复核驳回(待确认时直接作废;已确认后退回时同步删除其能耗记录)
BATCH_PENDING = "pending"
BATCH_CONFIRMED = "confirmed"
BATCH_REJECTED = "rejected"
BATCH_STATUSES = (BATCH_PENDING, BATCH_CONFIRMED, BATCH_REJECTED)


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

    batch_id 非空表示该记录由批量导入批次确认生成:记录与批次一起锁定,
    不再允许单条编辑/删除,只能通过整批退回作废后重新上传修订。
    batch_id 为空表示批次功能上线前的历史记录或其他途径录入,仍可单条维护。
    """

    __tablename__ = "energy_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    consumption: Mapped[float] = mapped_column(Float, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    facility: Mapped[Facility] = relationship(back_populates="records")
    batch: Mapped["ImportBatch | None"] = relationship(back_populates="records")


class ImportBatch(Base):
    """月度能耗表整批导入:一次上传 = 一个批次,走"导入—复核—出数"链路。

    同一文件内容(content_hash 为按解析后的有效单元格归一化计算的 SHA256)
    在仍处于 pending/confirmed 状态的批次中唯一,重复上传直接拒绝,
    避免同一份表反复导入制造重复记录;驳回后允许重新上传。
    """

    __tablename__ = "import_batches"
    __table_args__ = (
        # 部分唯一索引:仅对未驳回批次生效(SQLite 同样支持该语法)
        Index(
            "uq_import_batch_active_hash",
            "content_hash",
            unique=True,
            sqlite_where=sql_text("status != 'rejected'"),
            postgresql_where=sql_text("status <> 'rejected'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=BATCH_PENDING, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)  # CSV 数据行数(不含表头)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    # 整批合法行若全部确认后的汇总影响(tCO2e,未匹配行不计)
    impact_tco2e: Mapped[float] = mapped_column(Float, default=0.0)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    records: Mapped[list["EnergyRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class ImportRow(Base):
    """批次内的一行:合法行(is_valid=True)在批次确认时转为 EnergyRecord;
    错误行保留原始单元格与逐字段错误,供复核员追踪,永远不计入排放量。"""

    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)  # CSV 行号(含表头,首行数据=2)
    is_valid: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    facility_id: Mapped[int | None] = mapped_column(
        ForeignKey("facilities.id"), nullable=True
    )
    facility_code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    facility_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    period: Mapped[str] = mapped_column(String(7), nullable=False, default="")
    consumption: Mapped[float | None] = mapped_column(Float, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[str | None] = mapped_column(Text)  # JSON: [{"field": ..., "message": ...}]
    raw_data: Mapped[str | None] = mapped_column(Text)  # JSON: 原始单元格,便于错误行核对修正

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")
    facility: Mapped[Facility | None] = relationship()
