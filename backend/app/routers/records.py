from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/records", tags=["records"])


def to_out(record: models.EnergyRecord) -> schemas.EnergyRecordOut:
    return schemas.EnergyRecordOut(
        id=record.id,
        facility_id=record.facility_id,
        facility_name=record.facility.name,
        factor_id=record.factor_id,
        energy_type=record.factor.energy_type,
        factor_name=record.factor.name_zh,
        scope=record.factor.scope,
        category=record.factor.category,
        unit=record.factor.unit,
        period=record.period,
        consumption=record.consumption,
        emissions_tco2e=round(record.emissions_tco2e, 6),
        remark=record.remark,
        created_at=record.created_at,
    )


@router.get("", response_model=list[schemas.EnergyRecordOut])
def list_records(
    facility_id: int | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    scope: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.EnergyRecord).options(
        joinedload(models.EnergyRecord.facility), joinedload(models.EnergyRecord.factor)
    )
    if facility_id:
        q = q.filter(models.EnergyRecord.facility_id == facility_id)
    if period_from:
        q = q.filter(models.EnergyRecord.period >= period_from)
    if period_to:
        q = q.filter(models.EnergyRecord.period <= period_to)
    if scope:
        q = q.join(models.EmissionFactor).filter(models.EmissionFactor.scope == scope)
    records = q.order_by(models.EnergyRecord.period.desc(), models.EnergyRecord.id.desc()).all()
    return [to_out(r) for r in records]


@router.post("", response_model=schemas.EnergyRecordOut, status_code=201)
def create_record(payload: schemas.EnergyRecordCreate, db: Session = Depends(get_db)):
    if not db.get(models.Facility, payload.facility_id):
        raise HTTPException(404, "厂区不存在")
    if not db.get(models.EmissionFactor, payload.factor_id):
        raise HTTPException(404, "排放因子不存在")
    record = models.EnergyRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return to_out(record)


@router.delete("/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.get(models.EnergyRecord, record_id)
    if not record:
        raise HTTPException(404, "记录不存在")
    db.delete(record)
    db.commit()
