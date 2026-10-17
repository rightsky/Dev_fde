"""최초 기동 시 기준 데이터 적재: 관리자 계정, 분류체계, 기관."""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Organization, TaxonomyAxis, TaxonomyCode, TaxonomySet, User
from .security import hash_password
from .services.reference import taxonomy_seed

log = logging.getLogger("fde.seed")

# 목업 시나리오(국토교통)에서 쓰던 기관. FDE_SEED_DEMO_ORGS=false 로 끌 수 있다.
DEMO_ORGS = [
    ("ORG-1613000", "국토교통부"),
    ("ORG-1360000", "기상청"),
    ("ORG-1320000", "경찰청"),
    ("ORG-B552016", "한국교통안전공단"),
    ("ORG-6410000", "경기도"),
]


SET_AXES = ("F1", "F2", "F3", "F4", "F5", "F6")


def seed(db: Session) -> None:
    s = get_settings()
    if not db.scalar(select(func.count()).select_from(User)):
        password = s.admin_password or secrets.token_urlsafe(12)
        db.add(User(username=s.admin_username, password_hash=hash_password(password), name=s.admin_name, role="admin"))
        if not s.admin_password:
            log.warning("초기 관리자 계정 생성 — ID: %s / 비밀번호: %s (최초 로그인 후 변경하세요)", s.admin_username, password)
    # 기본 분류체계 세트 (v0.20): 이관 0011 이 만들지만, 이관이 비어 있는 DB 를 먼저 돈 경우를 위해 여기서도 보장한다
    base = db.scalar(select(TaxonomySet).where(TaxonomySet.slug == "base"))
    if base is None:
        base = TaxonomySet(slug="base", name="국토교통부 ARD 분류체계 (기본)", scope="국토교통부",
                           description="공공데이터 AI 친화적 관리 가이드라인 표 기반 기본 세트 (F1 주제영역 · F2 데이터유형 · F3 해상도 · F4 이용조건 · F5 AI활용목적 · F6 거버넌스)",
                           is_default=True, locked=True, created_label="시스템")
        db.add(base)
        db.flush()
    if not db.scalar(select(func.count()).select_from(TaxonomyAxis)):
        for pos, axis in enumerate(taxonomy_seed()["axes"]):
            ax = TaxonomyAxis(code=axis["code"], name=axis["name"], nature=axis["nature"], multi=axis["multi"],
                              version=axis.get("version"), rdf_property=axis.get("rdf_property"),
                              description=axis.get("description"), position=pos)
            for cpos, c in enumerate(axis["codes"]):
                ax.codes.append(TaxonomyCode(code=c["code"], label=c["label"], definition=c.get("definition"), position=cpos, extra=c.get("extra", {}),
                                             set_id=base.id if axis["code"] in SET_AXES else None))
            db.add(ax)
    if s.seed_demo_orgs and not db.scalar(select(func.count()).select_from(Organization)):
        for code, label in DEMO_ORGS:
            db.add(Organization(code=code, label=label))
    db.commit()
