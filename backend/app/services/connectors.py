"""기관 DB 스키마 읽기 커넥터 (데이터 패브릭 외부 연계).

원칙: 테이블 · 컬럼 · 자료형 · 널 허용 · 기본키만 읽는다. 행 데이터 · 예시값 · 통계는 읽지 않는다 (N²SF 부담 최소, 메타데이터 중심).
접속은 읽기 전용 세션으로 열고, 비밀번호는 FDE_SECRET_KEY 에서 파생한 키로 암호화해 저장한다.
가져온 테이블은 원천 자산(source=dbschema) 하나씩이 되어 STEP 1 후보 · 데이터 사전 · 기관 등급표 매칭에 그대로 쓰인다.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any
from urllib.parse import quote_plus

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Asset, DbConnector, utcnow
from . import profiling

KINDS = {
    "postgresql": {"label": "PostgreSQL", "port": 5432, "driver": "postgresql+psycopg", "default_schema": "public"},
    "mysql": {"label": "MySQL · MariaDB", "port": 3306, "driver": "mysql+pymysql", "default_schema": None},
}
MAX_TABLES = 500
MAX_COLUMNS = 2000


class ConnectorError(Exception):
    pass


def _fernet() -> Fernet:
    secret = get_settings().secret_key or ""
    if not secret:
        raise ConnectorError("FDE_SECRET_KEY 가 없어 접속 정보를 암호화할 수 없습니다")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("fde-connector:" + secret).encode("utf-8")).digest()))


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ConnectorError("저장된 비밀번호를 풀 수 없습니다 (FDE_SECRET_KEY 가 바뀌었으면 커넥터를 다시 등록하세요)") from exc


def url_of(c: DbConnector, password: str) -> str:
    k = KINDS[c.kind]
    return f"{k['driver']}://{quote_plus(c.username)}:{quote_plus(password)}@{c.host}:{c.port}/{c.database}"


def _engine(c: DbConnector, password: str):
    kw: dict[str, Any] = {"pool_pre_ping": True, "connect_args": {}}
    if c.kind == "postgresql":
        # 세션을 읽기 전용으로, 오래 걸리는 질의는 끊는다
        kw["connect_args"] = {"connect_timeout": 8, "options": "-c default_transaction_read_only=on -c statement_timeout=15000"}
    elif c.kind == "mysql":
        kw["connect_args"] = {"connect_timeout": 8, "read_timeout": 15}
    return create_engine(url_of(c, password), **kw)


def _normalize_type(t: Any) -> str:
    s = str(t).upper()
    if any(x in s for x in ("INT", "SERIAL", "BIGINT", "SMALLINT")) and "POINT" not in s:
        return "integer"
    if any(x in s for x in ("NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "REAL", "MONEY")):
        return "number"
    if any(x in s for x in ("TIMESTAMP", "DATE", "TIME")):
        return "datetime"
    if "BOOL" in s or s in ("BIT", "BIT(1)"):
        return "boolean"
    return "string"


def reflect(c: DbConnector, password: str) -> dict[str, Any]:
    """스키마만 읽는다. {schema, tables:[{name, comment, columns:[{name,type,raw_type,nullable,pk,comment}]}]}."""
    eng = _engine(c, password)
    try:
        with eng.connect() as conn:
            if c.kind == "mysql":
                conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
            insp = inspect(conn)
            schema = c.db_schema or KINDS[c.kind]["default_schema"]
            names = sorted(insp.get_table_names(schema=schema))
            if len(names) > MAX_TABLES:
                raise ConnectorError(f"테이블이 {len(names)}개라 상한({MAX_TABLES})을 넘습니다 — 스키마를 나눠 등록하세요")
            tables = []
            ncols = 0
            for name in names:
                cols = insp.get_columns(name, schema=schema)
                try:
                    pk = set(insp.get_pk_constraint(name, schema=schema).get("constrained_columns") or [])
                except Exception:  # noqa: BLE001
                    pk = set()
                try:
                    comment = (insp.get_table_comment(name, schema=schema) or {}).get("text")
                except Exception:  # noqa: BLE001
                    comment = None
                tables.append({"name": name, "comment": comment,
                               "columns": [{"name": col["name"], "type": _normalize_type(col["type"]), "raw_type": str(col["type"]),
                                            "nullable": bool(col.get("nullable", True)), "pk": col["name"] in pk, "comment": col.get("comment")}
                                           for col in cols]})
                ncols += len(cols)
                if ncols > MAX_COLUMNS:
                    raise ConnectorError(f"컬럼 수가 상한({MAX_COLUMNS})을 넘습니다 — 스키마를 나눠 등록하세요")
            return {"schema": schema, "tables": tables}
    finally:
        eng.dispose()


def test_connection(c: DbConnector, password: str) -> dict[str, Any]:
    r = reflect(c, password)
    return {"ok": True, "schema": r["schema"], "tables": len(r["tables"]), "columns": sum(len(t["columns"]) for t in r["tables"]),
            "sample": [t["name"] for t in r["tables"][:10]]}


def _profile_for(table: dict[str, Any], schema: str | None, connector: DbConnector) -> profiling.ProfileResult:
    """값 없이 구조만으로 프로파일을 만든다 (스트림과 같은 꼴). 예시값 · 통계는 비운다."""
    cols = []
    for col in table["columns"]:
        c = {"name": col["name"], "type": col["type"], "count": 0, "missing": 0, "null_rate": 0.0, "distinct": 0,
             "unique": bool(col["pk"]), "samples": [], "max_len": 0, "missing_markers": [], "raw_type": col["raw_type"],
             "nullable": col["nullable"], "pk": col["pk"]}
        if col.get("comment"):
            c["comment"] = col["comment"]
        pii = profiling._detect_pii(col["name"], [])  # noqa: SLF001 - 이름 기준 탐지만 (값은 읽지 않는다)
        if pii:
            c["pii"] = pii
        cols.append(c)
    cands = profiling._key_candidates(table["name"], cols, {})  # noqa: SLF001
    for cand in cands:
        cand["distinct"], cand["sampled"] = 0, False
    warnings = ["DB 스키마에서 읽은 구조입니다. 행 데이터 · 예시값 · 결측률은 읽지 않았습니다"]
    return profiling.ProfileResult(
        profile={"status": "dbschema", "source": {"connector": connector.name, "kind": connector.kind, "schema": schema, "table": table["name"]},
                 "tables": [{"name": table["name"], "rows": 0, "truncated": False, "header_row": 0, "preamble": [], "columns": cols,
                             "sample_rows": [], "comment": table.get("comment")}],
                 "warnings": warnings},
        key_candidates=sorted(cands, key=lambda x: (-x["score"], x["code"])), data_form="정형", media_type=None)


def sync(db: Session, c: DbConnector, password: str, user_id: int | None) -> dict[str, Any]:
    """스키마를 읽어 테이블마다 원천 자산을 만들거나 갱신한다. 사라진 테이블의 자산은 지우지 않고 표시만 한다."""
    r = reflect(c, password)
    existing = {a.filename: a for a in db.scalars(select(Asset).where(Asset.connector_id == c.id, Asset.deleted_at.is_(None)))}
    created, updated, unchanged = [], [], []
    seen = set()
    for t in r["tables"]:
        key = f"{r['schema'] or ''}.{t['name']}" if r["schema"] else t["name"]
        seen.add(key)
        res = _profile_for(t, r["schema"], c)
        digest = hashlib.sha256(repr([(x["name"], x["raw_type"], x["nullable"], x["pk"]) for x in t["columns"]]).encode()).hexdigest()
        a = existing.get(key)
        if a is None:
            a = Asset(name=t["name"], kind="dataset", source="dbschema", connector_id=c.id, filename=key, ext=None, size=None, sha256=digest,
                      media_type=None, storage_key=None, data_form="정형", org_id=c.org_id,
                      description=(t.get("comment") or f"{c.name} · {key} (DB 스키마에서 가져옴)"),
                      profile=res.profile, key_candidates=res.key_candidates, key_samples={}, created_by=user_id)
            db.add(a)
            created.append(t["name"])
        elif a.sha256 != digest:
            a.sha256, a.profile, a.key_candidates = digest, res.profile, res.key_candidates
            if not a.description or a.description.endswith("(DB 스키마에서 가져옴)"):
                a.description = t.get("comment") or f"{c.name} · {key} (DB 스키마에서 가져옴)"
            updated.append(t["name"])
        else:
            unchanged.append(t["name"])
    missing = [k for k in existing if k not in seen]
    for k in missing:
        prof = dict(existing[k].profile or {})
        prof["warnings"] = sorted(set(prof.get("warnings", [])) | {"마지막 동기화에서 원천 DB 에 이 테이블이 없었습니다"})
        existing[k].profile = prof
    c.status, c.last_error, c.last_synced_at, c.table_count = "ok", None, utcnow(), len(r["tables"])
    db.flush()
    return {"schema": r["schema"], "tables": len(r["tables"]), "created": created, "updated": updated, "unchanged": len(unchanged), "missing": missing}


def out(c: DbConnector) -> dict[str, Any]:
    return {"id": c.id, "name": c.name, "kind": c.kind, "kind_label": KINDS.get(c.kind, {}).get("label", c.kind), "host": c.host, "port": c.port,
            "database": c.database, "schema": c.db_schema or KINDS.get(c.kind, {}).get("default_schema"), "username": c.username,
            "org_id": c.org_id, "note": c.note, "status": c.status, "last_error": c.last_error, "last_tested_at": c.last_tested_at,
            "last_synced_at": c.last_synced_at, "table_count": c.table_count, "created_at": c.created_at}
