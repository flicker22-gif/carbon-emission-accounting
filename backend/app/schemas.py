from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


def reject_null_required(model: BaseModel, fields: tuple[str, ...]) -> None:
    """更新接口专用:必填字段显式传 null 报参数错误(区别于"未传 = 不修改")。

    若放行至数据库层,非空列会被写入 NULL 而抛 IntegrityError(500)。
    """
    nulls = [f for f in fields if f in model.model_fields_set and getattr(model, f) is None]
    if nulls:
        raise ValueError(f"必填字段不能为 null: {', '.join(nulls)}")


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
    energy_type: str | None = None
    name_zh: str | None = None
    scope: int | None = Field(default=None, ge=1, le=3)
    category: str | None = None
    unit: str | None = None
    factor_value: float | None = Field(default=None, gt=0)
    region: str | None = None
    year: int | None = Field(default=None, ge=1990, le=2100)
    source: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check_nulls(self) -> Self:
        # source/note 为可空字段,显式传 null 表示清空,不在此列
        reject_null_required(self, ("energy_type", "name_zh", "scope", "category",
                                    "unit", "factor_value", "region", "year"))
        return self


class EmissionFactorOut(EmissionFactorCreate):
    id: int

    model_config = {"from_attributes": True}


class EnergyTypeOut(BaseModel):
    """能源类型选项(录入下拉用),取该类型任一因子的展示信息"""

    energy_type: str
    name_zh: str
    scope: int
    unit: str


# ---------- 因子变更影响试算 ----------
class FactorImpactPreviewRequest(BaseModel):
    """保存因子前的试算请求。factor_id 为 None 表示新增因子,否则表示编辑该因子。"""

    factor_id: int | None = None
    factor: EmissionFactorCreate


class FactorImpactYear(BaseModel):
    """按数据年度分解的受影响情况"""

    year: int
    records: int
    before_tco2e: float
    after_tco2e: float
    delta_tco2e: float


class FactorImpactRecord(BaseModel):
    """受影响记录明细(试算结果中仅返回前若干条抽样)"""

    record_id: int
    facility_name: str
    period: str
    energy_type: str
    consumption: float
    before_factor: str | None
    before_tco2e: float | None
    after_factor: str | None
    after_tco2e: float | None


class FactorImpactPreview(BaseModel):
    """试算结果:不落库,仅模拟应用变更后重算并对比"""

    affected_records: int
    total_before_tco2e: float
    total_after_tco2e: float
    delta_tco2e: float
    by_year: list[FactorImpactYear]
    samples: list[FactorImpactRecord]


# ---------- 能耗记录 ----------
class EnergyRecordCreate(BaseModel):
    facility_id: int
    energy_type: str
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")
    consumption: float = Field(gt=0)
    remark: str | None = None


class EnergyRecordUpdate(BaseModel):
    """已录入记录可修正的字段:月份/消耗量/备注;厂区与能源类型不可改"""

    period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                               description="YYYY-MM")
    consumption: float | None = Field(default=None, gt=0)
    remark: str | None = None

    @model_validator(mode="after")
    def _check_nulls(self) -> Self:
        # remark 可空,显式传 null 表示清空
        reject_null_required(self, ("period", "consumption"))
        return self


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
    batch_id: int | None = None  # 非空=批次导入且已锁定,不可单条编辑/删除
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


# ---------- 批量导入 ----------
class RowFieldError(BaseModel):
    field: str  # 出错的 CSV 列名(中文),整行级错误为 "__row__"
    message: str


class BatchRowOut(BaseModel):
    """批次内的一行(合法行带因子匹配结果;错误行带原始单元格与逐字段错误)"""

    id: int
    row_number: int
    is_valid: bool
    facility_id: int | None
    facility_code: str
    facility_name: str
    facility_region: str | None
    energy_type: str
    period: str
    consumption: float | None
    remark: str | None
    errors: list[RowFieldError]
    raw_data: dict[str, str]
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


class BatchOut(BaseModel):
    id: int
    filename: str
    content_hash: str
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    impact_tco2e: float  # 合法行确认后的汇总影响(未匹配行不计)
    unmatched_valid_rows: int  # 合法但未匹配到因子的行数(可追踪,不计排放)
    review_note: str | None
    created_at: datetime
    confirmed_at: datetime | None
    rejected_at: datetime | None
    # 仅在详情接口返回
    rows: list[BatchRowOut] | None = None
    # 重复上传同一内容时返回已存在批次的 id,方便前端直接跳转复核
    duplicate_of_batch_id: int | None = None

    model_config = {"from_attributes": True}


class BatchSummaryOut(BaseModel):
    """批次列表项:不含行明细"""

    id: int
    filename: str
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    impact_tco2e: float
    unmatched_valid_rows: int
    created_at: datetime
    confirmed_at: datetime | None
    rejected_at: datetime | None

    model_config = {"from_attributes": True}


class BatchReviewAction(BaseModel):
    review_note: str | None = None


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
    unmatched_records: int  # 已确认记录中未匹配到因子、未计入汇总的记录数
    pending_batches: int  # 待确认批次数(其数据尚未计入汇总)
    by_scope: list[ScopeSummary]
    by_category: list[CategorySummary]
    by_facility: list[FacilitySummary]
