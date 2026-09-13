from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, services
from ..database import get_db

router = APIRouter(prefix="/api/records", tags=["records"])


def to_out(record: models.EnergyRecord, factor: models.EmissionFactor | None,
           ) -> schemas.EnergyRecordOut:
    emissions = services.emissions_tco2e(record, factor)
    return schemas.EnergyRecordOut(
        id=record.id,
        facility_id=record.facility_id,
        facility_name=record.facility.name,
        facility_region=record.facility.region,
        energy_type=record.energy_type,
        period=record.period,
        consumption=record.consumption,
        remark=record.remark,
        created_at=record.created_at,
        batch_id=record.batch_id,
        matched=factor is not None,
        factor_id=factor.id if factor else None,
        factor_name=factor.name_zh if factor else None,
        factor_value=factor.factor_value if factor else None,
        factor_region=factor.region if factor else None,
        factor_year=factor.year if factor else None,
        scope=factor.scope if factor else None,
        category=factor.category if factor else None,
        unit=factor.unit if factor else None,
        emissions_tco2e=round(emissions, 6) if emissions is not None else None,
    )


def _attach_factors(records: list[models.EnergyRecord], db: Session,
                    ) -> list[schemas.EnergyRecordOut]:
    factors = services.load_all_factors(db)
    return [to_out(r, services.factor_for_record(factors, r)) for r in records]


@router.get("", response_model=list[schemas.EnergyRecordOut])
def list_records(
    facility_id: int | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    scope: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.EnergyRecord).options(joinedload(models.EnergyRecord.facility))
    if facility_id:
        q = q.filter(models.EnergyRecord.facility_id == facility_id)
    if period_from:
        q = q.filter(models.EnergyRecord.period >= period_from)
    if period_to:
        q = q.filter(models.EnergyRecord.period <= period_to)
    records = q.order_by(models.EnergyRecord.period.desc(), models.EnergyRecord.id.desc()).all()
    out = _attach_factors(records, db)
    if scope:
        out = [r for r in out if r.scope == scope]
    return out


@router.post("", response_model=schemas.EnergyRecordOut, status_code=201)
def create_record(payload: schemas.EnergyRecordCreate, db: Session = Depends(get_db)):
    facility = db.get(models.Facility, payload.facility_id)
    if not facility:
        raise HTTPException(404, "厂区不存在")
    known_types = {f.energy_type for f in services.load_all_factors(db)}
    if payload.energy_type not in known_types:
        raise HTTPException(400, f"未知能源类型 {payload.energy_type},请先在因子库中维护")

    record = models.EnergyRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    factor = services.factor_for_record(services.load_all_factors(db), record)
    return to_out(record, factor)


@router.put("/{record_id}", response_model=schemas.EnergyRecordOut)
def update_record(record_id: int, payload: schemas.EnergyRecordUpdate,
                  db: Session = Depends(get_db)):
    """修正已有记录的月份/消耗量/备注,排放量按当前因子重新匹配计算。

    批次导入并确认的记录已随批次锁定,只能整批退回后修订,不能单条修改。
    """
    record = db.get(models.EnergyRecord, record_id)
    if not record:
        raise HTTPException(404, "记录不存在")
    if record.batch_id is not None:
        raise HTTPException(409, f"该记录由导入批次 #{record.batch_id} 确认生成,已锁定;"
                                "请在「批量导入」中整批退回后修订")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    factor = services.factor_for_record(services.load_all_factors(db), record)
    return to_out(record, factor)


@router.delete("/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.get(models.EnergyRecord, record_id)
    if not record:
        raise HTTPException(404, "记录不存在")
    if record.batch_id is not None:
        raise HTTPException(409, f"该记录由导入批次 #{record.batch_id} 确认生成,已锁定;"
                                "不能单条删除,请使用整批退回")
    db.delete(record)
    db.commit()
