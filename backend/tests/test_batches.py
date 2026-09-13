"""批量导入链路接口测试:部分错误行、重复提交、状态转换、锁定与汇总口径。"""

from .conftest import csv_bytes, make_facility, upload


# ---------- 部分错误行:行号 + 字段错误,合法行照常入批 ----------

def test_import_partial_error_rows(client):
    fid = make_facility(client)
    rows = [
        ["F001", "华东一厂", "electricity", "2026-08", "10000", ""],   # 合法
        ["F999", "幽灵厂", "electricity", "2026-08", "100", ""],       # 厂区不存在
        ["F001", "华东一厂", "natural_gas", "2026-13", "100", ""],     # 月份非法
        ["F001", "华东一厂", "diesel", "2026-08", "abc", ""],          # 消耗量非数字
        ["F001", "华东一厂", "nuclear", "2026-08", "50", ""],          # 未知能源类型
        ["F001", "华东一厂", "外购电力", "2026/7", "2000", "补录"],     # 中文名+斜杠日期,合法
    ]
    resp = upload(client, rows)
    assert resp.status_code == 201, resp.text
    batch = resp.json()
    assert batch["status"] == "pending"
    assert batch["total_rows"] == 6
    assert batch["valid_rows"] == 2
    assert batch["error_rows"] == 4

    rows_out = batch["rows"]
    # 合法行排在前,错误行在后
    assert [r["row_number"] for r in rows_out if r["is_valid"]] == [2, 7]
    bad = {r["row_number"]: r for r in rows_out if not r["is_valid"]}
    assert [e["field"] for e in bad[3]["errors"]] == ["厂区编号"]
    assert [e["field"] for e in bad[4]["errors"]] == ["期间"]
    assert [e["field"] for e in bad[5]["errors"]] == ["消耗量"]
    assert [e["field"] for e in bad[6]["errors"]] == ["能源类型"]

    # 行 2:江苏厂 2026 → 江苏 2023 地区因子 0.5810
    r2 = next(r for r in rows_out if r["row_number"] == 2)
    assert r2["matched"] is True
    assert r2["factor_region"] == "江苏"
    assert r2["emissions_tco2e"] == round(10000 * 0.5810 / 1000, 6)
    # 行 7:中文名能识别、斜杠日期归一化为 YYYY-MM
    r7 = next(r for r in rows_out if r["row_number"] == 7)
    assert r7["energy_type"] == "electricity"
    assert r7["period"] == "2026-07"

    # 影响汇总只含合法行且按匹配因子计:(10000*0.5810 + 2000*0.5810)/1000 = 6.972
    assert batch["impact_tco2e"] == 6.972
    assert batch["unmatched_valid_rows"] == 0

    # 待确认期间:仪表盘与明细接口都看不到该批数据
    summary = client.get("/api/reports/summary").json()
    assert summary["total_tco2e"] == 0
    assert summary["pending_batches"] == 1
    assert client.get("/api/records").json() == []
    assert "华东一厂" not in client.get("/api/reports/export.csv").text


def test_import_file_level_errors(client):
    # 缺必需列
    bad_header = csv_bytes([["F001", "electricity", "2026-08", "1"]],
                           header=["厂区编号", "厂区名称", "能源类型", "期间", "备注"])
    resp = client.post(
        "/api/batches/import",
        files={"file": ("x.csv", bad_header, "text/csv")},
    )
    assert resp.status_code == 400
    assert "消耗量" in resp.json()["detail"]

    # 空文件
    resp = client.post(
        "/api/batches/import",
        files={"file": ("x.csv", b"", "text/csv")},
    )
    assert resp.status_code == 400

    # 非 CSV
    resp = client.post(
        "/api/batches/import",
        files={"file": ("x.xlsx", b"xx", "text/csv")},
    )
    assert resp.status_code == 400


# ---------- 重复提交 ----------

def test_duplicate_upload_rejected(client):
    fid = make_facility(client)
    rows = [["F001", "华东一厂", "electricity", "2026-08", "10000", ""]]

    first = upload(client, rows)
    assert first.status_code == 201
    batch_id = first.json()["id"]

    dup = upload(client, rows, filename="renamed.csv")  # 文件名不同、内容相同
    assert dup.status_code == 409
    assert str(batch_id) in dup.json()["detail"]

    # 只创建了一个批次、零条正式记录
    assert len(client.get("/api/batches").json()) == 1
    assert client.get("/api/records").json() == []

    # 驳回后同内容允许重新上传
    assert client.post(f"/api/batches/{batch_id}/reject").status_code == 200
    again = upload(client, rows)
    assert again.status_code == 201
    assert again.json()["id"] != batch_id


def test_duplicate_after_confirm_then_return(client):
    fid = make_facility(client)
    rows = [["F001", "华东一厂", "electricity", "2026-08", "10000", ""]]

    b1 = upload(client, rows).json()
    assert client.post(f"/api/batches/{b1['id']}/confirm").status_code == 200

    # 已确认期间重复上传仍然拒绝,不产生第二批
    assert upload(client, rows).status_code == 409
    assert len(client.get("/api/batches").json()) == 1

    # 退回修订:记录消失,同内容可重新上传
    ret = client.post(f"/api/batches/{b1['id']}/return",
                      json={"review_note": "数字填错"})
    assert ret.status_code == 200
    assert ret.json()["status"] == "rejected"
    assert client.get("/api/records").json() == []
    assert client.get("/api/reports/summary").json()["total_tco2e"] == 0

    b2 = upload(client, rows)
    assert b2.status_code == 201
    assert b2.json()["id"] != b1["id"]


def test_within_file_duplicate_row_flagged(client):
    fid = make_facility(client)
    rows = [
        ["F001", "华东一厂", "electricity", "2026-08", "10000", ""],
        ["F001", "华东一厂", "electricity", "2026-08", "20000", ""],  # 同厂/类型/月
    ]
    batch = upload(client, rows).json()
    assert batch["valid_rows"] == 1
    assert batch["error_rows"] == 1
    dup_row = next(r for r in batch["rows"] if not r["is_valid"])
    assert dup_row["row_number"] == 3
    assert any(e["field"] == "__row__" and "重复" in e["message"]
               for e in dup_row["errors"])


# ---------- 状态转换 ----------

def test_confirm_locks_records_and_blocks_edits(client):
    fid = make_facility(client)
    rows = [
        ["F001", "华东一厂", "electricity", "2026-08", "10000", ""],
        ["F001", "华东一厂", "natural_gas", "2026-08", "100", ""],
    ]
    batch = upload(client, rows).json()

    confirmed = client.post(f"/api/batches/{batch['id']}/confirm").json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None

    records = client.get("/api/records").json()
    assert len(records) == 2
    assert all(r["batch_id"] == batch["id"] for r in records)

    # 仪表盘与 CSV 默认只计已确认数据
    summary = client.get("/api/reports/summary").json()
    expected = 10000 * 0.5810 / 1000 + 100 * 2.162 / 1000
    assert summary["total_tco2e"] == round(expected, 4)
    assert summary["pending_batches"] == 0
    csv_text = client.get("/api/reports/export.csv").text
    assert "华东一厂" in csv_text and "已确认" not in csv_text

    rid = records[0]["id"]
    # 锁定记录不可单条改/删
    r = client.put(f"/api/records/{rid}", json={"consumption": 1})
    assert r.status_code == 409
    assert "锁定" in r.json()["detail"]
    assert client.delete(f"/api/records/{rid}").status_code == 409
    # 数据未变
    assert client.get("/api/records").json()[0]["batch_id"] == batch["id"]

    # 状态机:已确认不能再确认/驳回
    assert client.post(f"/api/batches/{batch['id']}/confirm").status_code == 409
    assert client.post(f"/api/batches/{batch['id']}/reject").status_code == 409


def test_confirm_overlap_with_existing_record_rejected(client):
    fid = make_facility(client)
    rows = [["F001", "华东一厂", "electricity", "2026-08", "10000", ""]]
    b1 = upload(client, rows).json()
    assert client.post(f"/api/batches/{b1['id']}/confirm").status_code == 200

    # 不同文件、数值不同但同一厂区/能源/月份:上传可入待确认(走复核),确认时拦截
    b2 = upload(client, [["F001", "华东一厂", "electricity", "2026-08", "12000", "修订?"]])
    assert b2.status_code == 201
    bid2 = b2.json()["id"]
    resp = client.post(f"/api/batches/{bid2}/confirm")
    assert resp.status_code == 409
    assert "重复" in resp.json()["detail"]
    # 未确认:仍只有第一批的 1 条记录计入
    assert len(client.get("/api/records").json()) == 1

    # 与手工录入重叠同样拦截
    bid3 = upload(client, [["F001", "华东一厂", "diesel", "2026-09", "50", ""]]).json()["id"]
    assert client.post("/api/records", json={
        "facility_id": fid, "energy_type": "diesel", "period": "2026-09", "consumption": 99,
    }).status_code == 201
    resp = client.post(f"/api/batches/{bid3}/confirm")
    assert resp.status_code == 409
    assert "手工录入" in resp.json()["detail"]


def test_pending_transitions_and_reject(client):
    fid = make_facility(client)
    rows = [["F001", "华东一厂", "electricity", "2026-08", "10000", ""]]
    bid = upload(client, rows).json()["id"]

    # 待确认不能"退回"(退回只针对已确认)
    assert client.post(f"/api/batches/{bid}/return").status_code == 409

    # 驳回是终态:不能再驳回/确认
    assert client.post(f"/api/batches/{bid}/reject",
                       json={"review_note": "格式不对"}).status_code == 200
    assert client.post(f"/api/batches/{bid}/confirm").status_code == 409
    assert client.post(f"/api/batches/{bid}/reject").status_code == 409
    assert client.post(f"/api/batches/{bid}/return").status_code == 409

    # 驳回后从未产生正式记录
    assert client.get("/api/records").json() == []


def test_confirm_batch_without_valid_rows(client):
    fid = make_facility(client)
    rows = [["F999", "幽灵厂", "electricity", "2026-08", "100", ""]]
    batch = upload(client, rows).json()
    assert batch["valid_rows"] == 0
    resp = client.post(f"/api/batches/{batch['id']}/confirm")
    assert resp.status_code == 400


def test_manual_records_not_locked(client):
    """非批次录入(历史/手工)仍可单条编辑删除,锁定只约束批次记录。"""
    fid = make_facility(client)
    created = client.post("/api/records", json={
        "facility_id": fid, "energy_type": "diesel",
        "period": "2026-08", "consumption": 100,
    })
    assert created.status_code == 201
    rid = created.json()["id"]
    assert created.json()["batch_id"] is None
    assert client.put(f"/api/records/{rid}", json={"consumption": 120}).status_code == 200
    assert client.delete(f"/api/records/{rid}").status_code == 204


# ---------- 未匹配因子:可追踪、不计排放 ----------

def test_unmatched_factor_tracked_but_not_counted(client):
    # 新疆厂用电 2019 年:电力因子最早只到 2022 年 → 无匹配
    make_facility(client, code="X01", name="西北厂", region="新疆")
    rows = [["X01", "西北厂", "electricity", "2019-05", "5000", ""]]
    batch = upload(client, rows).json()
    assert batch["valid_rows"] == 1
    assert batch["error_rows"] == 0
    assert batch["unmatched_valid_rows"] == 1
    assert batch["impact_tco2e"] == 0  # 未匹配不计排放

    r = batch["rows"][0]
    assert r["is_valid"] is True
    assert r["matched"] is False
    assert r["emissions_tco2e"] is None

    # 合法行仍可确认入库,但仪表盘/CSV 不计其排放量,仅作未匹配提示
    client.post(f"/api/batches/{batch['id']}/confirm")
    summary = client.get("/api/reports/summary").json()
    assert summary["total_tco2e"] == 0
    assert summary["unmatched_records"] == 1
    records = client.get("/api/records").json()
    assert len(records) == 1 and records[0]["matched"] is False

    csv_text = client.get("/api/reports/export.csv").text
    assert "西北厂" in csv_text and "未匹配" in csv_text


def test_facility_delete_blocked_by_batch_rows(client):
    fid = make_facility(client)
    # 只有错误行的批次同样构成审计引用
    rows = [["F001", "华东一厂", "nuclear", "2026-08", "1", ""]]
    upload(client, rows)
    resp = client.delete("/api/facilities/1")
    assert resp.status_code == 409

    # 无任何批次引用的厂区可以删除(其手工记录级联删除)
    fid2 = make_facility(client, code="F002", name="华南二厂", region="广东")
    assert client.delete(f"/api/facilities/{fid2}").status_code == 204


def test_batches_list_filter_and_404(client):
    fid = make_facility(client)
    rows = [["F001", "华东一厂", "electricity", "2026-08", "10000", ""]]
    bid = upload(client, rows).json()["id"]

    assert client.get("/api/batches?status=confirmed").json() == []
    pending = client.get("/api/batches?status=pending").json()
    assert len(pending) == 1
    assert pending[0]["unmatched_valid_rows"] == 0

    assert client.get("/api/batches?status=bogus").status_code == 400
    assert client.get("/api/batches/9999").status_code == 404

    client.post(f"/api/batches/{bid}/confirm")
    assert len(client.get("/api/batches?status=confirmed").json()) == 1
