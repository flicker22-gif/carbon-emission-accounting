from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from .database import Base, SessionLocal, engine
from .models import EmissionFactor
from .routers import batches, facilities, factors, records, reports
from .seed_factors import DEFAULT_FACTORS

app = FastAPI(title="碳排放核算工具 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facilities.router)
app.include_router(factors.router)
app.include_router(records.router)
app.include_router(batches.router)
app.include_router(reports.router)


# 旧版开发库平滑升级:create_all 只建新表,不会给已存在的表补列。
# 批次功能给 energy_records 增加了 batch_id,这里对旧库幂等补列(仅开发用,
# 正式环境请走迁移工具)。
def _ensure_batch_id_column():
    inspector = inspect(engine)
    if "energy_records" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("energy_records")}
    if "batch_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE energy_records ADD COLUMN batch_id INTEGER"))


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_batch_id_column()
    db = SessionLocal()
    try:
        if db.query(EmissionFactor).count() == 0:
            db.add_all([EmissionFactor(**f) for f in DEFAULT_FACTORS])
            db.commit()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
