"""月度能耗表整批导入服务:解析 — 逐行校验 — 去重 — 批次状态机。

链路:
  上传 CSV → 逐行校验(行号 + 字段错误) → 合法行进入 pending 批次
  → 复核确认:整批写入 energy_records 并锁定
  → 驳回(待确认)/退回(已确认,原子删除其记录)

未确认批次的合法行只存在于 import_rows,仪表盘与 CSV 天然不计入;
未匹配因子的合法行可追踪但排放量为 None,不计入汇总。
"""

import csv
import hashlib
import io
import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from . import models, services

# CSV 表头(中文)→ 内部字段。厂区名称仅用于展示/核对,不参与匹配。
COLUMN_MAP = {
    "厂区编号": "facility_code",
    "厂区名称": "facility_name",
    "能源类型": "energy_type",
    "期间": "period",
    "消耗量": "consumption",
    "备注": "remark",
}
REQUIRED_COLUMNS = ["厂区编号", "能源类型", "期间", "消耗量"]
# 去重哈希与行解析都按这个固定列序,避免列顺序变化导致同一文件哈希不同
HASH_COLUMNS = ["厂区编号", "厂区名称", "能源类型", "期间", "消耗量", "备注"]

PERIOD_RE = re.compile(r"^(\d{4})[-/](\d{1,2})$")


class ImportError(Exception):
    """文件级错误(无法解析为批次),由路由转为 400。"""


def decode_csv(raw: bytes) -> str:
    """Excel 导出的 CSV 可能是 UTF-8(BOM)或 GBK,依次尝试。"""
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportError("文件编码无法识别,请使用 UTF-8 或 GBK 编码的 CSV 文件")


def _norm_period(value: str) -> str | None:
    """接受 2026-01 / 2026-1 / 2026/1,归一化为 YYYY-MM;不合法返回 None。"""
    m = PERIOD_RE.match(value)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return f"{year:04d}-{month:02d}"


def _content_hash(header_index: dict[str, int], rows: list[list[str]]) -> str:
    """按解析后的单元格归一化(去空白、固定列序)计算 SHA256。

    只取已知列,列顺序调整/尾随空列不影响结果;错误行也参与,
    保证"同一份内容(含有错行的文件)重复上传"一定被识别。
    """
    lines = []
    for raw_cells in rows:
        cells = []
        for col in HASH_COLUMNS:
            idx = header_index.get(col)
            cells.append(raw_cells[idx].strip() if idx is not None and idx < len(raw_cells) else "")
        if not any(cells):
            continue  # 与解析时跳过空行保持一致
        lines.append("\x1f".join(cells))
    return hashlib.sha256("\x1e".join(lines).encode("utf-8")).hexdigest()


def find_active_batch(db: Session, content_hash: str) -> models.ImportBatch | None:
    """查找同一内容且仍有效(未驳回)的批次。驳回后允许重新上传。"""
    return (
        db.query(models.ImportBatch)
        .filter(
            models.ImportBatch.content_hash == content_hash,
            models.ImportBatch.status != models.BATCH_REJECTED,
        )
        .first()
    )


def parse_and_create_batch(db: Session, filename: str, raw: bytes) -> models.ImportBatch:
    """解析 CSV 并落库一个 pending 批次(含合法行与错误行)。

    调用方需先做 content_hash 去重;本函数不提交事务。
    """
    text = decode_csv(raw)
    reader = csv.reader(io.StringIO(text))
    all_rows = [row for row in reader]
    if not all_rows:
        raise ImportError("文件为空")

    header = [h.strip().lstrip("﻿") for h in all_rows[0]]
    header_index: dict[str, int] = {}
    for zh, field in COLUMN_MAP.items():
        if zh in header:
            header_index[zh] = header.index(zh)
    missing = [c for c in REQUIRED_COLUMNS if c not in header_index]
    if missing:
        raise ImportError(f"缺少必需列: {', '.join(missing)}")

    def cell(raw_cells: list[str], col: str) -> str:
        idx = header_index.get(col)
        if idx is None or idx >= len(raw_cells):
            return ""
        return raw_cells[idx].strip()

    data_rows = [(i + 2, row) for i, row in enumerate(all_rows[1:])
                 if any(c.strip() for c in row)]
    if not data_rows:
        raise ImportError("没有可导入的数据行")

    facilities = {f.code: f for f in db.query(models.Facility).all()}
    factors = services.load_all_factors(db)
    type_by_code = {f.energy_type: f for f in factors}
    type_by_name = {f.name_zh: f.energy_type for f in factors}

    content_hash = _content_hash(header_index, all_rows[1:])

    batch = models.ImportBatch(
        filename=filename,
        content_hash=content_hash,
        status=models.BATCH_PENDING,
        total_rows=len(data_rows),
    )
    db.add(batch)
    # 不 flush:批次尚未确认查重结果,查重查询不能看到本批次自身;
    # ImportRow 通过 batch.rows 级联保存,batch.id 由提交时回填。

    seen_keys: set[tuple[str, str, str]] = set()
    valid_count = 0
    impact = 0.0

    for row_number, raw_cells in data_rows:
        raw_data = {col: cell(raw_cells, col) for col in HASH_COLUMNS}
        errors: list[dict[str, str]] = []

        code = raw_data["厂区编号"]
        name = raw_data["厂区名称"]
        type_value = raw_data["能源类型"]
        period_raw = raw_data["期间"]
        consumption_raw = raw_data["消耗量"]
        remark = raw_data["备注"] or None

        facility = facilities.get(code) if code else None
        if not code:
            errors.append({"field": "厂区编号", "message": "厂区编号不能为空"})
        elif facility is None:
            errors.append({"field": "厂区编号", "message": f"厂区不存在: {code}"})

        if not type_value:
            errors.append({"field": "能源类型", "message": "能源类型不能为空"})
            energy_type = ""
        else:
            energy_type = type_value if type_value in type_by_code else type_by_name.get(type_value, "")
            if not energy_type:
                errors.append({
                    "field": "能源类型",
                    "message": f"未知能源类型: {type_value},请使用因子库中的类型代码或中文名",
                })

        period = _norm_period(period_raw) if period_raw else None
        if not period_raw:
            errors.append({"field": "期间", "message": "期间不能为空,格式 YYYY-MM"})
        elif period is None:
            errors.append({"field": "期间", "message": f"期间格式错误: {period_raw},应为 YYYY-MM"})

        consumption: float | None = None
        if not consumption_raw:
            errors.append({"field": "消耗量", "message": "消耗量不能为空"})
        else:
            try:
                consumption = float(consumption_raw)
                if consumption <= 0:
                    errors.append({"field": "消耗量", "message": "消耗量必须大于 0"})
                    consumption = None
            except ValueError:
                errors.append({"field": "消耗量", "message": f"消耗量不是数字: {consumption_raw}"})

        # 文件内重复行:同一(厂区, 能源类型, 期间)第二次出现即报错,
        # 否则一次确认就会制造互相重复的记录
        dedup_key = ""
        if facility is not None and energy_type and period:
            dedup_key = (facility.code, energy_type, period)
            if dedup_key in seen_keys:
                errors.append({
                    "field": "__row__",
                    "message": f"与本表中 {facility.code}/{energy_type} 在 {period} 期间的另一行重复",
                })

        is_valid = not errors
        if is_valid:
            seen_keys.add(dedup_key)
            valid_count += 1
            shim = _RowShim(energy_type, period, consumption, facility.region)
            factor = services.factor_for_record(factors, shim)
            e = services.emissions_tco2e(shim, factor)
            if e is not None:
                impact += e

        row = models.ImportRow(
            row_number=row_number,
            is_valid=1 if is_valid else 0,
            facility_id=facility.id if facility is not None else None,
            facility_code=code,
            facility_name=name or (facility.name if facility is not None else ""),
            energy_type=energy_type or (type_value if type_value else ""),
            period=period or "",
            consumption=consumption if is_valid else None,
            remark=remark if is_valid else None,
            errors=json.dumps(errors, ensure_ascii=False) if errors else None,
            raw_data=json.dumps(raw_data, ensure_ascii=False),
        )
        batch.rows.append(row)

    batch.valid_rows = valid_count
    batch.error_rows = batch.total_rows - valid_count
    batch.impact_tco2e = round(impact, 4)
    return batch


class _RowShim:
    """因子匹配只需要 energy_type/period/consumption/facility.region,
    用轻量对象代替完整 EnergyRecord,使合法行在"尚未入库为记录"时即可试算。"""

    class _Facility:
        def __init__(self, region: str):
            self.region = region

    def __init__(self, energy_type: str, period: str, consumption: float, region: str):
        self.energy_type = energy_type
        self.period = period
        self.consumption = consumption
        self.facility = self._Facility(region)


# ---------- 批次状态机 ----------

class TransitionError(Exception):
    """非法状态转换,由路由转为 409。"""


def _confirmed_overlaps(
    db: Session, valid_rows: list[models.ImportRow]
) -> list[tuple[str, str, str, object]]:
    """找出合法行中与已存在正式记录(已确认批次或手工录入)键相同的行。

    键为(厂区, 能源类型, 期间)——同一厂区同一月同一能源只能有一条计数数据,
    否则月度汇总被重复累加。
    """
    keys = {(r.facility_id, r.energy_type, r.period) for r in valid_rows}
    if not keys:
        return []
    existing = (
        db.query(models.EnergyRecord, models.Facility.code)
        .join(models.Facility, models.EnergyRecord.facility_id == models.Facility.id)
        .all()
    )
    overlaps = []
    for rec, code in existing:
        if (rec.facility_id, rec.energy_type, rec.period) in keys:
            owner = rec.batch_id if rec.batch_id is not None else "手工录入"
            overlaps.append((code, rec.energy_type, rec.period, owner))
    return overlaps


def confirm_batch(db: Session, batch: models.ImportBatch,
                  review_note: str | None) -> models.ImportBatch:
    """pending → confirmed:合法行整批写入能耗记录并锁定。

    错误行不产生记录。批次与记录在同一事务提交,不存在"记录已写入但
    批次仍是待确认"的中间态。
    """
    if batch.status != models.BATCH_PENDING:
        raise TransitionError(
            f"批次当前状态为 {batch.status},仅待确认批次可以确认"
        )
    valid_rows = [r for r in batch.rows if r.is_valid]
    overlaps = _confirmed_overlaps(db, valid_rows)
    if overlaps:
        sample = "; ".join(
            f"{code}/{etype}/{period}(已在批次 #{bid})"
            for code, etype, period, bid in overlaps[:5]
        )
        raise TransitionError(
            f"本批有 {len(overlaps)} 行与已确认记录重复(厂区+能源类型+期间):{sample};"
            "请先退回原批次修订,或删除本批重复行后重新上传"
        )
    for row in valid_rows:
        db.add(models.EnergyRecord(
            facility_id=row.facility_id,
            energy_type=row.energy_type,
            period=row.period,
            consumption=row.consumption,
            remark=row.remark,
            batch_id=batch.id,
        ))
    batch.status = models.BATCH_CONFIRMED
    batch.confirmed_at = datetime.utcnow()
    if review_note is not None:
        batch.review_note = review_note
    db.commit()
    db.refresh(batch)
    return batch


def reject_batch(db: Session, batch: models.ImportBatch,
                 review_note: str | None) -> models.ImportBatch:
    """pending → rejected:整份表作废,不产生任何能耗记录。"""
    if batch.status != models.BATCH_PENDING:
        raise TransitionError(f"批次当前状态为 {batch.status},仅待确认批次可以驳回")
    batch.status = models.BATCH_REJECTED
    batch.rejected_at = datetime.utcnow()
    batch.review_note = review_note
    db.commit()
    db.refresh(batch)
    return batch


def return_batch(db: Session, batch: models.ImportBatch,
                 review_note: str | None) -> models.ImportBatch:
    """confirmed → rejected(退回/修订):整批锁定记录删除并标记驳回。

    删记录与改状态在同一事务提交,避免"旧汇总仍在、修订批次已上传"
    导致新旧数据同时可见。退回后同内容文件可重新上传(hash 仅对未驳回
    批次唯一),修订后再走确认。
    """
    if batch.status != models.BATCH_CONFIRMED:
        raise TransitionError(f"批次当前状态为 {batch.status},仅已确认批次可以退回")
    for record in list(batch.records):
        db.delete(record)
    batch.status = models.BATCH_REJECTED
    batch.confirmed_at = None
    batch.rejected_at = datetime.utcnow()
    batch.review_note = review_note
    db.commit()
    db.refresh(batch)
    return batch
