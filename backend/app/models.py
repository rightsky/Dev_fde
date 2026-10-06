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
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

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


class Asset(Base):
    __tablename__ = "asset"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))  # 표시 이름 (파일명에서 확장자 제거, 또는 스트림 토픽)
    kind: Mapped[str] = mapped_column(String(20))  # dataset | stream
    source: Mapped[str] = mapped_column(String(20), default="upload")  # upload | stream
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
