"""接口测试公共夹具:每个测试用独立临时 SQLite 库 + 种子因子。"""

import os
import tempfile

import pytest

# 必须在导入 app.* 之前指定数据库
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EmissionFactor  # noqa: E402
from app.seed_factors import DEFAULT_FACTORS  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all([EmissionFactor(**f) for f in DEFAULT_FACTORS])
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def make_facility(client, code="F001", name="华东一厂", region="江苏"):
    resp = client.post("/api/facilities", json={
        "name": name, "code": code, "region": region,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def csv_bytes(rows: list[list[str]], header=None) -> bytes:
    import csv
    import io

    header = header or ["厂区编号", "厂区名称", "能源类型", "期间", "消耗量", "备注"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def upload(client, rows: list[list[str]], filename="monthly.csv"):
    return client.post(
        "/api/batches/import",
        files={"file": (filename, csv_bytes(rows), "text/csv")},
    )
