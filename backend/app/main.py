"""FDE Data Studio API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Route

from . import mcp_server
from .config import get_settings
from .db import SessionLocal, engine
from .migrate import upgrade as migrate_db
from .routers import agents, catalog, core, studio
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate_db(engine)  # 테이블 생성·변경은 Alembic 이관 파일로만 한다
    with SessionLocal() as db:
        seed(db)
    if not get_settings().secret_key:
        logging.getLogger("fde").warning("FDE_SECRET_KEY 미설정 — 재기동하면 발급된 로그인 토큰이 모두 만료됩니다")
    async with mcp_server.running():  # AI 에이전트용 MCP 서버 (/api/mcp)
        yield


app = FastAPI(title="FDE Data Studio API", version="0.5.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

for r in (core.router, studio.router, catalog.router, agents.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# MCP: 가이드라인 3.4.5 MCP 연계 관리 원칙. 키 없는 요청은 401, 모든 도구 호출은 agent_call 에 기록
app.router.routes.append(Route(mcp_server.PATH, endpoint=mcp_server.MCPEndpoint(), methods=["GET", "POST", "DELETE"]))
