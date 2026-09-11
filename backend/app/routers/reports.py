import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _query_records(db: Session, period_from: str | None, period_to: str | None,
                   facility_id: int | None):
    q = db.query(models.EnergyRecord).options(
        joinedload(models.EnergyRecord.facility), joinedload(models.EnergyRecord.factor)
    )
    if period_from:
        q = q.filter(models.EnergyRecord.period >= period_from)
    if period_to:
        q = q.filter(models.EnergyRecord.period <= period_to)
    if facility_id:
        q = q.filter(models.EnergyRecord.facility_id == facility_id)
    return q.all()


@router.get("/summary", response_model=schemas.ReportSummary)
def summary(
    period_from: str | None = None,
    period_to: str | None = None,
    facility_id: int | None = None,
    db: Session = Depends(get_db),
):
    """按范围一/二/三分类汇总排放量（tCO2e）"""
    records = _query_records(db, period_from, period_to, facility_id)

    by_scope: dict[int, float] = defaultdict(float)
    by_category: dict[tuple[int, str], float] = defaultdict(float)
    by_facility: dict[tuple[int, str, int], float] = defaultdict(float)

    for r in records:
        e = r.emissions_tco2e
        scope = r.factor.scope
        by_scope[scope] += e
        by_category[(scope, r.factor.category)] += e
        by_facility[(r.facility_id, r.facility.name, scope)] += e

    return schemas.ReportSummary(
        period_from=period_from,
        period_to=period_to,
        total_tco2e=round(sum(by_scope.values()), 4),
        by_scope=[schemas.ScopeSummary(scope=s, emissions_tco2e=round(v, 4))
                  for s, v in sorted(by_scope.items())],
        by_category=[schemas.CategorySummary(scope=s, category=c, emissions_tco2e=round(v, 4))
                     for (s, c), v in sorted(by_category.items())],
        by_facility=[schemas.FacilitySummary(facility_id=fid, facility_name=name,
                                             scope=s, emissions_tco2e=round(v, 4))
                     for (fid, name, s), v in sorted(by_facility.items())],
    )


@router.get("/export.csv")
def export_csv(
    period_from: str | None = None,
    period_to: str | None = None,
    facility_id: int | None = None,
    db: Session = Depends(get_db),
):
    """导出明细 CSV（GHG Protocol 报告底稿）"""
    records = _query_records(db, period_from, period_to, facility_id)

    buf = io.StringIO()
    buf.write("﻿")  # BOM，便于 Excel 识别中文
    writer = csv.writer(buf)
    writer.writerow(["厂区", "期间", "范围", "类别", "能源类型", "消耗量", "单位",
                     "排放因子(kgCO2e/单位)", "排放量(tCO2e)", "备注"])
    for r in records:
        writer.writerow([
            r.facility.name, r.period, f"范围{r.factor.scope}", r.factor.category,
            r.factor.name_zh, r.consumption, r.factor.unit,
            r.factor.factor_value, round(r.emissions_tco2e, 6), r.remark or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ghg_emissions.csv"},
    )
