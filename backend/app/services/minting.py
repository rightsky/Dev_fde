"""식별자 발급.

- 초안 ID   : `DST-draft-000012` 처럼 ProcessDataset 번호에서 결정적으로 만든다. 발행물에 남으면 게이트 0 ④ 위반이다.
- 발행 ID   : 민팅 대장(MintRecord)에 등록된 것만 쓴다. 대장에 없으면 None 을 돌려주며, 호출 측이 즉석에서 만들어 쓰지 않는다
              (fallback 발급 금지). 발급은 관리자가 명시적으로 수행한다.
- Activity  : `ACT-K-0421` 형태의 일련번호. 기록 시점에 즉시 확정 발급한다.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Asset, MintRecord, Process, ProcessDataset, Sequence, User

SEQ_START = {"DST": 1, "SVC": 1, "ACT": 421, "ORG": 1}
DRAFT_PATTERN = r"(-신규|-draft-|-미민팅-)"


def next_seq(db: Session, kind: str) -> int:
    seq = db.get(Sequence, kind, with_for_update=True)
    if seq is None:
        seq = Sequence(kind=kind, next_value=SEQ_START.get(kind, 1))
        db.add(seq)
        db.flush()
    value = seq.next_value
    seq.next_value = value + 1
    db.flush()
    return value


def kind_of(asset: Asset) -> str:
    return "SVC" if asset.kind == "stream" else "DST"


def draft_id(pd: ProcessDataset) -> str:
    return f"{kind_of(pd.asset)}-draft-{pd.id:06d}"


def minted_record(db: Session, asset_id: int) -> MintRecord | None:
    return db.scalar(select(MintRecord).where(MintRecord.asset_id == asset_id))


def resource_id(db: Session, pd: ProcessDataset, mode: str) -> tuple[str, bool]:
    """(본체 ID, 민팅 여부). 발행 모드에서 대장에 없으면 '-미민팅-' 표식 ID 를 돌려준다."""
    if mode == "publish":
        rec = minted_record(db, pd.asset_id)
        if rec:
            return rec.minted_id, True
        return f"{kind_of(pd.asset)}-미민팅-{pd.id:06d}", False
    return draft_id(pd), False


def mint_for_process(db: Session, process: Process, user: User) -> list[MintRecord]:
    """조합 데이터셋 중 대장에 없는 것에 발행 ID 를 발급한다."""
    created: list[MintRecord] = []
    for pd in process.combo:
        if minted_record(db, pd.asset_id):
            continue
        kind = kind_of(pd.asset)
        rec = MintRecord(kind=kind, minted_id=f"{kind}-{next_seq(db, kind):06d}", asset_id=pd.asset_id,
                         process_id=process.id, minted_by=user.id, note=f"프로세스 「{process.name}」에서 발급")
        db.add(rec)
        db.flush()
        created.append(rec)
    return created


# ------------------------------------------------------------------ IRI 규칙
def id_ns() -> str:
    return get_settings().id_ns


def def_ns() -> str:
    return get_settings().def_ns


def resource_iri(rid: str) -> str:
    return f"{id_ns()}{'service' if rid.startswith('SVC-') else 'dataset'}/{rid}"


def distribution_id(rid: str, ext: str | None) -> str:
    tail = rid.split("-", 1)[1] if "-" in rid else rid
    return f"DIST-{tail}-{(ext or 'bin').lower()}"


def distribution_iri(rid: str, ext: str | None) -> str:
    return f"{id_ns()}distribution/{distribution_id(rid, ext)}"


def org_iri(code: str) -> str:
    return f"{id_ns()}org/{code}"


def activity_iri(code: str) -> str:
    return f"{id_ns()}activity/{code}"


def agent_iri(key: str = "fde-studio") -> str:
    return f"{id_ns()}agent/{key}"


def concept_iri(code: str) -> str:
    return f"{def_ns()}concept/{code}"


def scheme_iri(axis: str) -> str:
    return f"{def_ns()}scheme/{axis}"


def collection_id(process: Process, mode: str) -> str:
    return f"COL-{process.id:06d}" if mode == "publish" else f"COL-draft-{process.id:06d}"


def collection_iri(process: Process, mode: str) -> str:
    return f"{id_ns()}collection/{collection_id(process, mode)}"


def relation_iri(rel_id: int) -> str:
    return f"{id_ns()}relation/REL-{rel_id:06d}"
