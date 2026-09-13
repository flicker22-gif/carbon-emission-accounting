"""批量导入批次接口:上传 → 复核(有效记录/错误行/汇总影响)→ 确认/驳回/退回。"""

import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import import_service, models, schemas, services
from ..database import get_db

router = APIRouter(prefix="/api/batches", tags=["batches"])

IMPORT_HEADERS = ["厂区编号", "厂区名称", "能源类型", "期间", "消耗量", "备注"]


def _factor_for_row(factors, row: models.ImportRow) -> models.EmissionFactor | None:
    """合法行复用既有 地区优先+年度最新+全国兜底 匹配;错误行不参与。"""
    if not row.is_valid or row.facility is None:
        return None
    shim = import_service._RowShim(
        row.energy_type, row.period, row.consumption or 0.0, row.facility.region
    )
    return services.factor_for_record(factors, shim)


def _row_to_out(row: models.ImportRow, factor: models.EmissionFactor | None
                ) -> schemas.BatchRowOut:
    errors = [schemas.RowFieldError(**e) for e in json.loads(row.errors)] if row.errors else []
    raw_data = json.loads(row.raw_data) if row.raw_data else {}

    if row.is_valid and factor is not None and row.consumption is not None:
        emissions = row.consumption * factor.factor_value / 1000.0
    else:
        # 错误行或未匹配因子:排放量恒为空,不计入任何汇总
        emissions = None

    return schemas.BatchRowOut(
        id=row.id,
        row_number=row.row_number,
        is_valid=bool(row.is_valid),
        facility_id=row.facility_id,
        facility_code=row.facility_code,
        facility_name=row.facility_name,
        facility_region=row.facility.region if row.facility is not None else None,
        energy_type=row.energy_type,
        period=row.period,
        consumption=row.consumption,
        remark=row.remark,
        errors=errors,
        raw_data=raw_data,
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


def _detail(db: Session, batch: models.ImportBatch,
            duplicate_of: int | None = None) -> schemas.BatchOut:
    """详情:合法行在前、错误行在后(各自按行号),含逐行动态因子匹配。"""
    factors = services.load_all_factors(db)
    ordered = sorted(batch.rows, key=lambda r: (not r.is_valid, r.row_number))
    rows_out = [_row_to_out(r, _factor_for_row(factors, r)) for r in ordered]
    unmatched = sum(1 for r in rows_out if r.is_valid and not r.matched)
    return schemas.BatchOut(
        id=batch.id,
        filename=batch.filename,
        content_hash=batch.content_hash,
        status=batch.status,
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        error_rows=batch.error_rows,
        impact_tco2e=batch.impact_tco2e,
        unmatched_valid_rows=unmatched,
        review_note=batch.review_note,
        created_at=batch.created_at,
        confirmed_at=batch.confirmed_at,
        rejected_at=batch.rejected_at,
        rows=rows_out,
        duplicate_of_batch_id=duplicate_of,
    )


def _summary(db: Session, batch: models.ImportBatch, factors) -> schemas.BatchSummaryOut:
    unmatched = sum(
        1 for r in batch.rows if r.is_valid and _factor_for_row(factors, r) is None
    )
    return schemas.BatchSummaryOut(
        id=batch.id,
        filename=batch.filename,
        status=batch.status,
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        error_rows=batch.error_rows,
        impact_tco2e=batch.impact_tco2e,
        unmatched_valid_rows=unmatched,
        created_at=batch.created_at,
        confirmed_at=batch.confirmed_at,
        rejected_at=batch.rejected_at,
    )


def _get_batch(db: Session, batch_id: int) -> models.ImportBatch:
    batch = (
        db.query(models.ImportBatch)
        .options(joinedload(models.ImportBatch.rows).joinedload(models.ImportRow.facility))
        .filter_by(id=batch_id)
        .first()
    )
    if not batch:
        raise HTTPException(404, "批次不存在")
    return batch


@router.get("", response_model=list[schemas.BatchSummaryOut])
def list_batches(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.ImportBatch).options(
        joinedload(models.ImportBatch.rows).joinedload(models.ImportRow.facility)
    )
    if status:
        if status not in models.BATCH_STATUSES:
            raise HTTPException(400, f"非法状态 {status}")
        q = q.filter(models.ImportBatch.status == status)
    batches = q.order_by(models.ImportBatch.id.desc()).all()
    factors = services.load_all_factors(db)
    return [_summary(db, b, factors) for b in batches]


@router.get("/template.csv")
def download_template():
    """导入模板:含表头与一行示例(填报前请删除示例行)。"""
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(IMPORT_HEADERS)
    writer.writerow(["F001", "示例厂区", "electricity", "2026-08", "12500", ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=energy_import_template.csv"},
    )


@router.post("/import", response_model=schemas.BatchOut, status_code=201)
async def import_batch(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传整份月度能耗表:逐行校验,合法行进入同一个待确认批次。

    - 合法行/错误行同批保留,错误行带行号与字段错误,不影响合法行入批;
    - 同一文件内容重复上传(原批次未驳回)返回 409,不创建任何记录;
    - 未匹配因子的合法行保留可追踪,但排放量为空、不计入汇总。
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "仅支持 .csv 文件")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "上传文件为空")

    try:
        batch = import_service.parse_and_create_batch(db, file.filename, raw)
    except import_service.ImportError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))

    duplicate = import_service.find_active_batch(db, batch.content_hash)
    if duplicate is not None:
        db.rollback()
        status_label = "待确认" if duplicate.status == models.BATCH_PENDING else "已确认"
        raise HTTPException(
            409,
            f"相同内容已存在{status_label}批次 #{duplicate.id},"
            f"重复上传不会创建记录;如需修订请先退回该批次",
        )

    try:
        db.commit()
    except IntegrityError:
        # 并发上传同一内容:部分唯一索引兜底
        db.rollback()
        raise HTTPException(409, "相同内容的批次已存在(并发提交),请勿重复上传")
    return _detail(db, _get_batch(db, batch.id))


@router.get("/{batch_id}", response_model=schemas.BatchOut)
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    return _detail(db, _get_batch(db, batch_id))


@router.post("/{batch_id}/confirm", response_model=schemas.BatchOut)
def confirm_batch(batch_id: int, payload: schemas.BatchReviewAction | None = None,
                  db: Session = Depends(get_db)):
    """确认批次:合法行整批写入能耗记录并锁定,错误行保留在批次中供追溯。"""
    batch = _get_batch(db, batch_id)
    if batch.status != models.BATCH_PENDING:
        raise HTTPException(409, f"批次当前状态为 {batch.status},仅待确认批次可以确认")
    if batch.valid_rows == 0:
        raise HTTPException(400, "批次没有任何合法行,无法确认;请修正后整份重新上传")
    note = payload.review_note if payload else None
    try:
        import_service.confirm_batch(db, batch, note)
    except import_service.TransitionError as exc:
        db.rollback()
        raise HTTPException(409, str(exc))
    return _detail(db, _get_batch(db, batch_id))


@router.post("/{batch_id}/reject", response_model=schemas.BatchOut)
def reject_batch(batch_id: int, payload: schemas.BatchReviewAction | None = None,
                 db: Session = Depends(get_db)):
    """驳回待确认批次:整份作废,不产生记录;驳回后同内容可重新上传。"""
    batch = _get_batch(db, batch_id)
    note = payload.review_note if payload else None
    try:
        import_service.reject_batch(db, batch, note)
    except import_service.TransitionError as exc:
        db.rollback()
        raise HTTPException(409, str(exc))
    return _detail(db, _get_batch(db, batch_id))


@router.post("/{batch_id}/return", response_model=schemas.BatchOut)
def return_batch(batch_id: int, payload: schemas.BatchReviewAction | None = None,
                 db: Session = Depends(get_db)):
    """退回已确认批次以修订:锁定记录删除与批次驳回在同一事务完成,
    避免旧汇总与修订后新数据同时可见。"""
    batch = _get_batch(db, batch_id)
    note = payload.review_note if payload else None
    try:
        import_service.return_batch(db, batch, note)
    except import_service.TransitionError as exc:
        db.rollback()
        raise HTTPException(409, str(exc))
    return _detail(db, _get_batch(db, batch_id))
