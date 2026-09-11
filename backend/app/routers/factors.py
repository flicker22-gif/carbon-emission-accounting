from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/factors", tags=["factors"])


@router.get("", response_model=list[schemas.EmissionFactorOut])
def list_factors(scope: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.EmissionFactor)
    if scope:
        q = q.filter(models.EmissionFactor.scope == scope)
    return q.order_by(models.EmissionFactor.scope, models.EmissionFactor.id).all()


@router.post("", response_model=schemas.EmissionFactorOut, status_code=201)
def create_factor(payload: schemas.EmissionFactorCreate, db: Session = Depends(get_db)):
    if db.query(models.EmissionFactor).filter_by(energy_type=payload.energy_type).first():
        raise HTTPException(409, f"能源类型 {payload.energy_type} 已存在")
    factor = models.EmissionFactor(**payload.model_dump())
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return factor


@router.put("/{factor_id}", response_model=schemas.EmissionFactorOut)
def update_factor(factor_id: int, payload: schemas.EmissionFactorUpdate,
                  db: Session = Depends(get_db)):
    factor = db.get(models.EmissionFactor, factor_id)
    if not factor:
        raise HTTPException(404, "排放因子不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(factor, key, value)
    db.commit()
    db.refresh(factor)
    return factor
