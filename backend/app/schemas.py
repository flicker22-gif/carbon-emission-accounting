from datetime import datetime

from pydantic import BaseModel, Field


# ---------- 厂区 ----------
class FacilityCreate(BaseModel):
    name: str
    code: str
    region: str = "全国"
    location: str | None = None
    industry: str | None = None


class FacilityOut(FacilityCreate):
    id: int

    model_config = {"from_attributes": True}


# ---------- 排放因子 ----------
class EmissionFactorCreate(BaseModel):
    energy_type: str
    name_zh: str
    scope: int = Field(ge=1, le=3)
    category: str
    unit: str
    factor_value: float = Field(gt=0)
    region: str = "全国"
    year: int = Field(ge=1990, le=2100)
    source: str | None = None
    note: str | None = None


class EmissionFactorUpdate(BaseModel):
    name_zh: str | None = None
    scope: int | None = Field(default=None, ge=1, le=3)
    category: str | None = None
    unit: str | None = None
    factor_value: float | None = Field(default=None, gt=0)
    region: str | None = None
    year: int | None = Field(default=None, ge=1990, le=2100)
    source: str | None = None
    note: str | None = None


class EmissionFactorOut(EmissionFactorCreate):
    id: int

    model_config = {"from_attributes": True}


class EnergyTypeOut(BaseModel):
    """能源类型选项(录入下拉用),取该类型任一因子的展示信息"""

    energy_type: str
    name_zh: str
    scope: int
    unit: str


# ---------- 能耗记录 ----------
class EnergyRecordCreate(BaseModel):
    facility_id: int
    energy_type: str
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")
    consumption: float = Field(gt=0)
    remark: str | None = None


class EnergyRecordOut(BaseModel):
    id: int
    facility_id: int
    facility_name: str
    facility_region: str
    energy_type: str
    period: str
    consumption: float
    remark: str | None
    created_at: datetime
    # 以下为动态匹配到的因子信息;未匹配到时为 None
    matched: bool
    factor_id: int | None
    factor_name: str | None
    factor_value: float | None
    factor_region: str | None
    factor_year: int | None
    scope: int | None
    category: str | None
    unit: str | None
    emissions_tco2e: float | None

    model_config = {"from_attributes": True}


# ---------- 报表 ----------
class ScopeSummary(BaseModel):
    scope: int
    emissions_tco2e: float


class CategorySummary(BaseModel):
    scope: int
    category: str
    emissions_tco2e: float


class FacilitySummary(BaseModel):
    facility_id: int
    facility_name: str
    scope: int
    emissions_tco2e: float


class ReportSummary(BaseModel):
    period_from: str | None
    period_to: str | None
    total_tco2e: float
    unmatched_records: int  # 未匹配到因子、未计入汇总的记录数
    by_scope: list[ScopeSummary]
    by_category: list[CategorySummary]
    by_facility: list[FacilitySummary]
