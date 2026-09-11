from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/factors", tags=["factors"])


@router.get("", response_model=list[schemas.EmissionFactorOut])
def list_factors(
    energy_type: str | None = None,
    region: str | None = None,
    year: int | None = None,
    scope: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.EmissionFactor)
    if energy_type:
        q = q.filter(models.EmissionFactor.energy_type == energy_type)
    if region:
        q = q.filter(models.EmissionFactor.region == region)
    if year:
        q = q.filter(models.EmissionFactor.year == year)
    if scope:
        q = q.filter(models.EmissionFactor.scope == scope)
    return q.order_by(
        models.EmissionFactor.energy_type,
        models.EmissionFactor.region,
        models.EmissionFactor.year.desc(),
    ).all()


@router.get("/energy-types", response_model=list[schemas.EnergyTypeOut])
def list_energy_types(db: Session = Depends(get_db)):
    """录入下拉用的能源类型列表(去重)"""
    factors = db.query(models.EmissionFactor).order_by(models.EmissionFactor.scope).all()
    seen: dict[str, schemas.EnergyTypeOut] = {}
    for f in factors:
        if f.energy_type not in seen:
            seen[f.energy_type] = schemas.EnergyTypeOut(
                energy_type=f.energy_type, name_zh=f.name_zh, scope=f.scope, unit=f.unit
            )
    return list(seen.values())


@router.post("", response_model=schemas.EmissionFactorOut, status_code=201)
def create_factor(payload: schemas.EmissionFactorCreate, db: Session = Depends(get_db)):
    dup = db.query(models.EmissionFactor).filter_by(
        energy_type=payload.energy_type, region=payload.region, year=payload.year
    ).first()
    if dup:
        raise HTTPException(
            409,
            f"已存在 {payload.energy_type}/{payload.region}/{payload.year} 的因子,"
            f"请使用 PUT /api/factors/{dup.id} 更新",
        )
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
    data = payload.model_dump(exclude_unset=True)
    # 若改了组合键,检查不与其他因子冲突
    new_key = (
        data.get("energy_type", factor.energy_type),
        data.get("region", factor.region),
        data.get("year", factor.year),
    )
    dup = db.query(models.EmissionFactor).filter_by(
        energy_type=new_key[0], region=new_key[1], year=new_key[2]
    ).first()
    if dup and dup.id != factor_id:
        raise HTTPException(409, f"已存在 {new_key[0]}/{new_key[1]}/{new_key[2]} 的因子")
    for key, value in data.items():
        setattr(factor, key, value)
    db.commit()
    db.refresh(factor)
    return factor


@router.delete("/{factor_id}", status_code=204)
def delete_factor(factor_id: int, db: Session = Depends(get_db)):
    factor = db.get(models.EmissionFactor, factor_id)
    if not factor:
        raise HTTPException(404, "排放因子不存在")
    db.delete(factor)
    db.commit()
