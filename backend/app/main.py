from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .models import EmissionFactor
from .routers import facilities, factors, records, reports
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
app.include_router(reports.router)


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
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
