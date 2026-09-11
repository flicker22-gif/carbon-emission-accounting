"""排放因子自动匹配服务。

匹配规则（对一条能耗记录:能源类型 + 厂区地区 + 数据期间）:
1. 能源类型相同;
2. 因子适用年度 <= 数据期间所在年度(取满足条件的最新年度);
3. 地区优先:厂区所在省份的因子优先,无则回退到"全国"兜底因子。
"""

from sqlalchemy.orm import Session, joinedload

from . import schemas
from .models import DEFAULT_REGION, EmissionFactor, EnergyRecord


def resolve_factor(
    factors: list[EmissionFactor],
    energy_type: str,
    region: str,
    year: int,
) -> EmissionFactor | None:
    """从候选因子中匹配最优因子:地区精确优先,其次年度最新。"""
    candidates = [
        f for f in factors
        if f.energy_type == energy_type and f.year <= year
        and f.region in (region, DEFAULT_REGION)
    ]
    if not candidates:
        return None
    # 地区精确匹配优先于全国兜底,同优先级下取年度最新
    return max(candidates, key=lambda f: (f.region == region, f.year))


def load_all_factors(db: Session) -> list[EmissionFactor]:
    return db.query(EmissionFactor).all()


def factor_for_record(
    factors: list[EmissionFactor], record: EnergyRecord
) -> EmissionFactor | None:
    year = int(record.period[:4])
    return resolve_factor(factors, record.energy_type, record.facility.region, year)


def emissions_tco2e(record: EnergyRecord, factor: EmissionFactor | None) -> float | None:
    """排放量(tCO2e) = 活动数据 × 因子(kgCO2e) / 1000;无匹配因子时返回 None。"""
    if factor is None:
        return None
    return record.consumption * factor.factor_value / 1000.0


# ---------- 因子变更影响试算 ----------

SAMPLE_LIMIT = 10  # 试算结果中返回的受影响记录抽样条数


def describe_factor(factor: EmissionFactor | None) -> str | None:
    """因子简述,用于试算明细展示,如 "外购电力(全国 2023年) 0.5366"。"""
    if factor is None:
        return None
    return f"{factor.name_zh}({factor.region} {factor.year}年) {factor.factor_value}"


def preview_factor_impact(
    db: Session, factor_id: int | None, data: dict
) -> schemas.FactorImpactPreview:
    """模拟应用一次因子变更(新增,或覆盖 factor_id 对应因子),重算全部记录并对比。

    不落库:构造一个未入库的"影子因子"参与匹配。匹配因子或排放量发生变化的
    记录计为受影响记录;总量差值 = 受影响记录变更前后排放量之差(未受影响
    记录两侧相等,不影响差值)。
    """
    before_factors = load_all_factors(db)
    after_factors = [f for f in before_factors if f.id != factor_id]
    ghost = EmissionFactor(id=factor_id if factor_id is not None else -1, **data)
    after_factors.append(ghost)

    records = (
        db.query(EnergyRecord)
        .options(joinedload(EnergyRecord.facility))
        .order_by(EnergyRecord.period, EnergyRecord.id)
        .all()
    )

    affected: list[tuple[EnergyRecord, EmissionFactor | None, float | None,
                         EmissionFactor | None, float | None]] = []
    for r in records:
        fb = factor_for_record(before_factors, r)
        fa = factor_for_record(after_factors, r)
        eb = emissions_tco2e(r, fb)
        ea = emissions_tco2e(r, fa)
        if (fb.id if fb else None) == (fa.id if fa else None) and eb == ea:
            continue
        affected.append((r, fb, eb, fa, ea))

    total_before = sum(eb for _, _, eb, _, _ in affected if eb is not None)
    total_after = sum(ea for _, _, _, _, ea in affected if ea is not None)

    by_year: dict[int, list[float]] = {}
    year_records: dict[int, int] = {}
    for r, _, eb, _, ea in affected:
        y = int(r.period[:4])
        year_records[y] = year_records.get(y, 0) + 1
        agg = by_year.setdefault(y, [0.0, 0.0])
        agg[0] += eb if eb is not None else 0.0
        agg[1] += ea if ea is not None else 0.0

    return schemas.FactorImpactPreview(
        affected_records=len(affected),
        total_before_tco2e=round(total_before, 4),
        total_after_tco2e=round(total_after, 4),
        delta_tco2e=round(total_after - total_before, 4),
        by_year=[
            schemas.FactorImpactYear(
                year=y,
                records=year_records[y],
                before_tco2e=round(v[0], 4),
                after_tco2e=round(v[1], 4),
                delta_tco2e=round(v[1] - v[0], 4),
            )
            for y, v in sorted(by_year.items())
        ],
        samples=[
            schemas.FactorImpactRecord(
                record_id=r.id,
                facility_name=r.facility.name,
                period=r.period,
                energy_type=r.energy_type,
                consumption=r.consumption,
                before_factor=describe_factor(fb),
                before_tco2e=round(eb, 6) if eb is not None else None,
                after_factor=describe_factor(fa),
                after_tco2e=round(ea, 6) if ea is not None else None,
            )
            for r, fb, eb, fa, ea in affected[:SAMPLE_LIMIT]
        ],
    )
