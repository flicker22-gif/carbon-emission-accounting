from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists
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
    # 批次行(含合法/错误行、任意状态批次)是审计与复核线索,
    # 已确认批次的能耗记录也已锁定;有此类引用时不允许删厂区,
    # 避免批次详情与汇总出现悬挂数据
    referenced = db.query(
        exists().where(models.ImportRow.facility_id == facility_id)
    ).scalar()
    if referenced:
        raise HTTPException(
            409, "该厂在导入批次中存在数据(含已确认/驳回批次),请先处理相关批次后再删除"
        )
    db.delete(facility)
    db.commit()
