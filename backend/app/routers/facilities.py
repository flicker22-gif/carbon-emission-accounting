from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("", response_model=list[schemas.FacilityOut])
def list_facilities(db: Session = Depends(get_db)):
    return db.query(models.Facility).order_by(models.Facility.id).all()


@router.post("", response_model=schemas.FacilityOut, status_code=201)
def create_facility(payload: schemas.FacilityCreate, db: Session = Depends(get_db)):
    if db.query(models.Facility).filter_by(code=payload.code).first():
        raise HTTPException(409, f"厂区编码 {payload.code} 已存在")
    facility = models.Facility(**payload.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


@router.delete("/{facility_id}", status_code=204)
def delete_facility(facility_id: int, db: Session = Depends(get_db)):
    facility = db.get(models.Facility, facility_id)
    if not facility:
        raise HTTPException(404, "厂区不存在")
    db.delete(facility)
    db.commit()
