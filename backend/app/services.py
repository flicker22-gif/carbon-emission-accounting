"""排放因子自动匹配服务。

匹配规则（对一条能耗记录:能源类型 + 厂区地区 + 数据期间）:
1. 能源类型相同;
2. 因子适用年度 <= 数据期间所在年度(取满足条件的最新年度);
3. 地区优先:厂区所在省份的因子优先,无则回退到"全国"兜底因子。
"""

from sqlalchemy.orm import Session

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
