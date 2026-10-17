"""데이터 모델.

핵심 개념
- Asset          : 수집 후보 원천 (업로드 파일 또는 등록 스트림). 프로파일 결과를 보관한다.
- Process        : 8단계 워크플로 1회 수행 단위 (작업 프로세스).
- ProcessDataset : 프로세스에 편입된 원천 1건. 메타데이터·분류·확정 상태의 소유자이며 정본 그래프의 입력이다.
- Relation       : 프로세스 내 데이터셋 간 관계 (JOINED_ON / GROUPED_WITH / DERIVED_FROM).
- Activity       : prov:Activity 로그. 사람·시스템의 모든 확정·실행을 기록한다.
- ValidationRun / SerializationRun / DiagnosisRun : STEP 6·7·8 실행 기록.
- MintRecord     : 발행 ID 대장. 발급 이력이 없는 리소스는 발행할 수 없다.
- CatalogEntry   : 발행된 카탈로그 항목.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """항상 UTC 시간대가 붙은 datetime 으로 읽고 쓴다 (SQLite 는 시간대를 저장하지 않으므로 읽을 때 붙인다)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)  # KST 등 다른 시간대로 들어온 값도 UTC 로 맞춰 저장 (SQLite 는 오프셋을 버린다)

    def process_result_value(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)  # PostgreSQL 은 세션 시간대로 돌려주므로 UTC 로 맞춘다


class Organization(Base):
    __tablename__ = "organization"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # 예: ORG-1613000
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="organization")
    note: Mapped[str | None] = mapped_column(String(400), default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="worker")  # admin | worker | viewer
    org_label: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # 비밀번호를 바꾼 시각. 이보다 먼저 발급된 토큰은 무효 (비밀번호 변경 뒤 기존 로그인 끊기)
    password_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class Asset(Base):
    __tablename__ = "asset"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))  # 표시 이름 (파일명에서 확장자 제거, 또는 스트림 토픽)
    kind: Mapped[str] = mapped_column(String(20))  # dataset | stream
    source: Mapped[str] = mapped_column(String(20), default="upload")  # upload | stream | dbschema
    connector_id: Mapped[int | None] = mapped_column(ForeignKey("db_connector.id", ondelete="SET NULL"), default=None, index=True)
    filename: Mapped[str | None] = mapped_column(String(300), default=None)
    ext: Mapped[str | None] = mapped_column(String(20), default=None)
    size: Mapped[int | None] = mapped_column(Integer, default=None)
    sha256: Mapped[str | None] = mapped_column(String(64), default=None)
    media_type: Mapped[str | None] = mapped_column(String(200), default=None)
    storage_key: Mapped[str | None] = mapped_column(String(300), default=None)
    data_form: Mapped[str | None] = mapped_column(String(40), default=None)  # 정형 | 반정형 | 비정형 | 실시간 스트림
    description: Mapped[str | None] = mapped_column(Text, default=None)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organization.id"), default=None)
    # 프로파일: {status, error?, tables:[{name, rows, header_row, columns:[...]}], warnings:[...]}
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 연계키 후보: [{code, table, column, score, reason}]
    key_candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # 연계키 후보 컬럼의 정규화된 고유값 표본 (결합 후보 계산용): {"table|column": [values...]}
    key_samples: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 스트림 전용: {temporal_resolution, event_time_column, endpoint_url, timezone, fields:[{name,type}]}
    stream: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    org: Mapped[Organization | None] = relationship()
    connector: Mapped[DbConnector | None] = relationship(foreign_keys=[connector_id])


class Process(Base):
    __tablename__ = "process"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | trashed
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    combo_title: Mapped[str | None] = mapped_column(String(300), default=None)
    combo_description: Mapped[str | None] = mapped_column(Text, default=None)
    combo_source: Mapped[str | None] = mapped_column(String(30), default=None)  # manual | suggestion
    combo_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    pub_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    lineage_waiver_reason: Mapped[str | None] = mapped_column(Text, default=None)
    lineage_waived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # 조합(결합) 등급: 기본은 구성 데이터셋 최고 등급. 담당자가 낮추면 사유 필수 (가이드라인 3.6.1 결합 후 재검토)
    combo_grade: Mapped[str | None] = mapped_column(String(10), default=None)  # O · S1 · S2 · C
    combo_grade_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    trashed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    datasets: Mapped[list[ProcessDataset]] = relationship(
        back_populates="process", cascade="all, delete-orphan", order_by="ProcessDataset.position"
    )
    relations: Mapped[list[Relation]] = relationship(
        back_populates="process", cascade="all, delete-orphan", order_by="Relation.priority"
    )
    owner: Mapped[User | None] = relationship(foreign_keys=[created_by])  # 담당자 (만든 사람 또는 관리자가 배정한 사람)

    @property
    def combo(self) -> list[ProcessDataset]:
        return [d for d in self.datasets if d.in_combo]


class ProcessDataset(Base):
    __tablename__ = "process_dataset"
    __table_args__ = (UniqueConstraint("process_id", "asset_id", name="uq_pd_process_asset"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    selected: Mapped[bool] = mapped_column(Boolean, default=True)  # STEP 1 후보 선택
    in_combo: Mapped[bool] = mapped_column(Boolean, default=False)  # STEP 2 조합 편입
    position: Mapped[int] = mapped_column(Integer, default=0)
    # STEP 3 메타데이터 값 (services/canonical.py 의 META_FIELDS 참조)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 승인이 필요한 ARD 필수 필드 중 사람이 승인한 필드 이름 목록
    approved_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    extra_classes: Mapped[list[str]] = mapped_column(JSON, default=list)
    meta_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # STEP 4 분류: {"F1": ["도로"], ..., "K": [{"code": "K5", "table": "...", "column": "..."}], "N2SF": "O"}
    classification: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    class_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    authoring_activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    process: Mapped[Process] = relationship(back_populates="datasets")
    asset: Mapped[Asset] = relationship()
    authoring_activity: Mapped[Activity | None] = relationship(foreign_keys=[authoring_activity_id])


class Relation(Base):
    __tablename__ = "relation"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(30))  # JOINED_ON | GROUPED_WITH | DERIVED_FROM
    source_id: Mapped[int] = mapped_column(ForeignKey("process_dataset.id", ondelete="CASCADE"))
    target_id: Mapped[int] = mapped_column(ForeignKey("process_dataset.id", ondelete="CASCADE"))
    key_code: Mapped[str | None] = mapped_column(String(10), default=None)  # K1..K9
    source_table: Mapped[str | None] = mapped_column(String(200), default=None)
    source_column: Mapped[str | None] = mapped_column(String(200), default=None)
    target_table: Mapped[str | None] = mapped_column(String(200), default=None)
    target_column: Mapped[str | None] = mapped_column(String(200), default=None)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # SSOT 우선순위 (작을수록 우선)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | confirmed
    # 실측 결합 통계: {source_distinct, target_distinct, matched, source_match_rate, target_match_rate, sampled}
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    process: Mapped[Process] = relationship(back_populates="relations")
    source: Mapped[ProcessDataset] = relationship(foreign_keys=[source_id])
    target: Mapped[ProcessDataset] = relationship(foreign_keys=[target_id])


class TaxonomyAxis(Base):
    __tablename__ = "taxonomy_axis"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # F1..F6, K, N2SF
    name: Mapped[str] = mapped_column(String(100))
    nature: Mapped[str] = mapped_column(String(10))  # 필수 | 권장 | 보조
    multi: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str | None] = mapped_column(String(40), default=None)
    rdf_property: Mapped[str | None] = mapped_column(String(100), default=None)
    description: Mapped[str | None] = mapped_column(String(400), default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)

    codes: Mapped[list[TaxonomyCode]] = relationship(
        back_populates="axis", cascade="all, delete-orphan", order_by="TaxonomyCode.position"
    )


class TaxonomyCode(Base):
    __tablename__ = "taxonomy_code"
    __table_args__ = (UniqueConstraint("axis_code", "code", name="uq_taxonomy_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    axis_code: Mapped[str] = mapped_column(ForeignKey("taxonomy_axis.code", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(40))  # IRI 로컬명 (예: F1-02, K5, N2SF-O)
    label: Mapped[str] = mapped_column(String(100))
    definition: Mapped[str | None] = mapped_column(String(400), default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 축별 부가 속성 (예: F3 {"group": "temporal", "duration": "PT5M"}, F4 {"property": "dcterms:license"})
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    axis: Mapped[TaxonomyAxis] = relationship(back_populates="codes")


class Sequence(Base):
    """ID 채번기. kind 별로 다음 번호를 보관한다."""

    __tablename__ = "id_sequence"
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class MintRecord(Base):
    """발행 ID 대장. 원천(Asset) 1건당 본체 ID 1개를 보증한다."""

    __tablename__ = "mint_record"
    __table_args__ = (UniqueConstraint("asset_id", name="uq_mint_asset"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))  # DST | SVC
    minted_id: Mapped[str] = mapped_column(String(40), unique=True)  # DST-000961
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    process_id: Mapped[int | None] = mapped_column(ForeignKey("process.id", ondelete="SET NULL"), default=None)
    minted_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    minted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    note: Mapped[str | None] = mapped_column(String(300), default=None)

    asset: Mapped[Asset] = relationship()


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # ACT-K-0421
    type: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    agent_type: Mapped[str] = mapped_column(String(20), default="person")  # person | software
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    actor_label: Mapped[str] = mapped_column(String(100), default="시스템")
    process_id: Mapped[int | None] = mapped_column(ForeignKey("process.id", ondelete="SET NULL"), default=None)
    dataset_id: Mapped[int | None] = mapped_column(Integer, default=None)  # ProcessDataset.id (FK 없이 보존)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class ValidationRun(Base):
    __tablename__ = "validation_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(10))  # draft | publish
    shapes_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="done")
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    # 실행 시점의 조합 서명 (조합 구성원·모드가 바뀌면 stale)
    combo_signature: Mapped[str] = mapped_column(String(64), default="")
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"), default=None)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    results: Mapped[list[ValidationDatasetResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ValidationDatasetResult.id"
    )
    activity: Mapped[Activity | None] = relationship()


class ValidationDatasetResult(Base):
    __tablename__ = "validation_dataset_result"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("validation_run.id", ondelete="CASCADE"))
    dataset_id: Mapped[int] = mapped_column(Integer)  # ProcessDataset.id
    dataset_name: Mapped[str] = mapped_column(String(300))
    resource_id: Mapped[str] = mapped_column(String(80))  # 검증 시점의 본체 ID
    checksum: Mapped[str] = mapped_column(String(64))
    gate0: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    conforms: Mapped[bool] = mapped_column(Boolean, default=False)  # SHACL Violation 0건
    passed: Mapped[bool] = mapped_column(Boolean, default=False)  # 게이트 0 통과 + conforms
    violation_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    info_count: Mapped[int] = mapped_column(Integer, default=0)
    # [{source, severity, shape, message, focus, path, value, route}]
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    report_ttl: Mapped[str | None] = mapped_column(Text, default=None)
    triple_count: Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped[ValidationRun] = relationship(back_populates="results")


class SerializationRun(Base):
    __tablename__ = "serialization_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"))
    validation_run_id: Mapped[int] = mapped_column(ForeignKey("validation_run.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(10))
    formats: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="done")
    ok_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    # [{dataset_id, name, resource_id, checksum, passed, checks:[{name, ok, detail}]}]
    self_verify: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"), default=None)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Artifact.id"
    )
    activity: Mapped[Activity | None] = relationship()


class Artifact(Base):
    __tablename__ = "artifact"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("serialization_run.id", ondelete="CASCADE"))
    dataset_id: Mapped[int] = mapped_column(Integer)
    dataset_name: Mapped[str] = mapped_column(String(300))
    fmt: Mapped[str] = mapped_column(String(10))  # ttl | jsonld | txt | schema
    filename: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    set_checksum: Mapped[str] = mapped_column(String(64))

    run: Mapped[SerializationRun] = relationship(back_populates="artifacts")


class DiagnosisRun(Base):
    __tablename__ = "diagnosis_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"))
    serialization_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("serialization_run.id", ondelete="SET NULL"), default=None
    )
    ruleset_version: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(default=0.0)
    max_score: Mapped[float] = mapped_column(default=0.0)
    # {areas:[...], methods:[...], roadmap:[...]}
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # [{id, area, name, method, status, score, basis, evidence:[...], datasets:[...], remedy, route}]
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"), default=None)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    activity: Mapped[Activity | None] = relationship()


class Attestation(Base):
    """HUMAN-ATTEST 항목에 대한 담당자 확인 (증빙 + 서명)."""

    __tablename__ = "attestation"
    __table_args__ = (UniqueConstraint("process_id", "item_id", name="uq_attestation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"))
    item_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10))  # met | partial | unmet
    note: Mapped[str | None] = mapped_column(Text, default=None)
    evidence: Mapped[str | None] = mapped_column(Text, default=None)
    attested_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    attested_label: Mapped[str] = mapped_column(String(100), default="")
    attested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"), default=None)


class CatalogEntry(Base):
    __tablename__ = "catalog_entry"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(40), unique=True)  # DST-000961 / SVC-000041
    iri: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))  # dataset | stream
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    publisher_label: Mapped[str | None] = mapped_column(String(200), default=None)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    process_id: Mapped[int | None] = mapped_column(ForeignKey("process.id", ondelete="SET NULL"), default=None)
    process_name: Mapped[str | None] = mapped_column(String(200), default=None)
    collection_title: Mapped[str | None] = mapped_column(String(300), default=None)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="published")  # published | withdrawn
    checksum: Mapped[str] = mapped_column(String(64))
    turtle: Mapped[str] = mapped_column(Text)
    jsonld: Mapped[str] = mapped_column(Text)
    text_summary: Mapped[str | None] = mapped_column(Text, default=None)
    schema_json: Mapped[str | None] = mapped_column(Text, default=None)
    # 검색·표시용 요약: {classification:{...}, keys:[...], media_type, form, triple_count, readiness}
    facets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    search_text: Mapped[str] = mapped_column(Text, default="")
    published_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    published_label: Mapped[str] = mapped_column(String(100), default="")
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activity.id"), default=None)


class AgentKey(Base):
    """AI 에이전트(MCP) 접근 키. 키 원문은 발급할 때 한 번만 보여 주고 해시만 저장한다 (가이드라인 3.4.5 표 39)."""

    __tablename__ = "agent_key"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # 사용처 (예: 정책분석팀 Claude)
    purpose: Mapped[str | None] = mapped_column(Text, default=None)  # 이용 목적
    prefix: Mapped[str] = mapped_column(String(16))  # 화면 표시용 앞자리
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256
    grades: Mapped[list[str]] = mapped_column(JSON, default=list)  # 접근 허용 N2SF 등급 (O · S). C 는 허용하지 않는다
    tools: Mapped[list[str]] = mapped_column(JSON, default=list)  # 허용 도구 (비면 전체 조회 도구)
    daily_limit: Mapped[int] = mapped_column(Integer, default=1000)  # 하루 호출 상한
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class AgentCall(Base):
    """AI 에이전트의 도구 호출 이력 (가이드라인 3.4.5 '이력 관리'). 거부된 호출도 남긴다."""

    __tablename__ = "agent_call"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_id: Mapped[int | None] = mapped_column(ForeignKey("agent_key.id", ondelete="SET NULL"), default=None, index=True)
    key_label: Mapped[str] = mapped_column(String(120), default="")
    tool: Mapped[str] = mapped_column(String(60))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resource_ids: Mapped[list[str]] = mapped_column(JSON, default=list)  # 응답에 담긴 데이터셋
    status: Mapped[str] = mapped_column(String(10))  # ok | denied | error
    message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class ReviewRequest(Base):
    """발행 검수 요청 (검수 큐). 담당자가 요청하고 관리자가 승인·반려한다.

    가이드라인 3.4.6 표 40 의 HITL: 제한공유 데이터·개인정보 포함·데이터 결합 같은 고위험 발행은 사람이 검토·승인한다.
    요청 시점의 변환 결과(serialization_run)와 데이터셋별 정본 체크섬을 묶어 두어, 승인하는 내용이 검토한 내용과 같음을 보장한다.
    """

    __tablename__ = "review_request"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending | approved | rejected | withdrawn
    message: Mapped[str | None] = mapped_column(Text, default=None)  # 요청 메모
    serialization_run_id: Mapped[int | None] = mapped_column(ForeignKey("serialization_run.id", ondelete="SET NULL"), default=None)
    checksums: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)  # 발행 ID → 정본 체크섬 (요청 시점)
    risk_level: Mapped[str] = mapped_column(String(8), default="low")  # high | medium | low
    signals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{code, severity, label, detail, datasets}]
    datasets: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # 요청 시점 요약
    diagnosis: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)  # {run_id, score, max_score, stale}
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    requested_label: Mapped[str] = mapped_column(String(100), default="")
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    reviewer_label: Mapped[str | None] = mapped_column(String(100), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    decision_note: Mapped[str | None] = mapped_column(Text, default=None)
    acknowledged: Mapped[list[str]] = mapped_column(JSON, default=list)  # 승인자가 확인한 고위험 신호 코드
    self_approved: Mapped[bool] = mapped_column(Boolean, default=False)  # 요청자가 직접 승인
    published: Mapped[list[str]] = mapped_column(JSON, default=list)  # 승인으로 발행된 발행 ID


class SimulationRun(Base):
    """STEP 7 AI 활용 시뮬레이션 실행 기록 (시연 때 다시 열어 볼 수 있게 결과를 저장한다)."""

    __tablename__ = "simulation_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id", ondelete="CASCADE"), index=True)
    scenario: Mapped[str] = mapped_column(String(20))  # chat | agent
    with_metadata: Mapped[bool] = mapped_column(Boolean, default=True)  # False = 메타데이터 없이(Before)
    dataset_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    question: Mapped[str] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # 답변·근거·도구 호출 이력
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(60), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[str | None] = mapped_column(String(40), default=None, index=True)  # Before/After 비교 묶음
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_label: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class OrgGradeEntry(Base):
    """기관이 N²SF 1단계(준비)에서 만든 업무정보 · 정보시스템 등급표의 한 행. 자산과 매칭해 데이터셋 등급 기본값과 충돌 신호에 쓴다."""
    __tablename__ = "org_grade_entry"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), default="info")  # info(업무정보) | system(정보시스템)
    name: Mapped[str] = mapped_column(String(300))
    system: Mapped[str | None] = mapped_column(String(200), default=None)  # 소관 정보시스템 (이름 또는 코드)
    department: Mapped[str | None] = mapped_column(String(200), default=None)
    grade: Mapped[str] = mapped_column(String(10))  # O · S1 · S2 · C
    personal_data: Mapped[str | None] = mapped_column(String(20), default=None)  # 기관표의 개인정보 포함 표기 (있을 때)
    legal_basis: Mapped[str | None] = mapped_column(String(500), default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id", ondelete="SET NULL"), default=None, index=True)  # 담당자가 확정한 매칭
    match_score: Mapped[int] = mapped_column(Integer, default=0)
    source_file: Mapped[str | None] = mapped_column(String(300), default=None)
    source_sha256: Mapped[str | None] = mapped_column(String(64), default=None)
    imported_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AgentGrant(Base):
    """에이전트 키에 대한 S2(제한 공유) 데이터셋 건별 승인. S2 는 키 등급만으로 열리지 않고 발행본마다 승인을 받아야 한다 (3.6.1 S2: 사전 승인 · 접근통제)."""
    __tablename__ = "agent_grant"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_id: Mapped[int] = mapped_column(ForeignKey("agent_key.id", ondelete="CASCADE"), index=True)
    resource_id: Mapped[str] = mapped_column(String(40), index=True)  # 발행 식별자 (DST-000002 등)
    note: Mapped[str | None] = mapped_column(Text, default=None)  # 승인 근거 (협약 번호, 목적 등)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    granted_label: Mapped[str] = mapped_column(String(100), default="")
    granted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class DbConnector(Base):
    """기관 DB 스키마 읽기 커넥터. 테이블 · 컬럼 · 자료형만 읽고 행 데이터는 읽지 않는다 (데이터 패브릭 외부 연계)."""
    __tablename__ = "db_connector"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))  # postgresql | mysql
    host: Mapped[str] = mapped_column(String(200))
    port: Mapped[int] = mapped_column(Integer)
    database: Mapped[str] = mapped_column(String(100))
    db_schema: Mapped[str | None] = mapped_column(String(100), default=None)  # 비우면 기본 스키마 (public 등)
    username: Mapped[str] = mapped_column(String(100))
    secret_enc: Mapped[str] = mapped_column(Text)  # Fernet 으로 암호화한 비밀번호 (FDE_SECRET_KEY 파생 키)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organization.id"), default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="never")  # never | ok | error
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_tested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    org: Mapped[Organization | None] = relationship()


class ShareLink(Base):
    """공유 링크 (ARD 관리). 수요처가 로그인 없이 만료형으로 산출물을 내려받는다. O · S1 등급만 허용, 토큰은 해시만 저장."""
    __tablename__ = "share_link"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(8), default="")  # 화면 표시용 앞 8자
    kind: Mapped[str] = mapped_column(String(20))  # file | zip | validation | diagnosis | package
    target_id: Mapped[int] = mapped_column(Integer)  # kind 별 대상 ID (artifact · run · dataset)
    dataset_id: Mapped[int | None] = mapped_column(Integer, default=None)
    process_id: Mapped[int | None] = mapped_column(ForeignKey("process.id", ondelete="SET NULL"), default=None)
    filename: Mapped[str] = mapped_column(String(300))
    grade: Mapped[str | None] = mapped_column(String(4), default=None)  # 만들 때의 등급 (O · S1)
    recipient: Mapped[str | None] = mapped_column(String(200), default=None)  # 받는 곳 (기관 · 담당자 메모)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    max_downloads: Mapped[int] = mapped_column(Integer, default=10)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), default=None)
    created_label: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
