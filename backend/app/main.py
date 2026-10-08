"""FDE Data Studio API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import SessionLocal, engine
from .migrate import upgrade as migrate_db
from .routers import catalog, core, studio
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_db(engine)  # 테이블 생성·변경은 Alembic 이관 파일로만 한다
    with SessionLocal() as db:
        seed(db)
    if not get_settings().secret_key:
        logging.getLogger("fde").warning("FDE_SECRET_KEY 미설정 — 재기동하면 발급된 로그인 토큰이 모두 만료됩니다")
    yield


app = FastAPI(title="FDE Data Studio API", version="0.4.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

for r in (core.router, studio.router, catalog.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
