"""정본 그래프 빌더.

ProcessDataset 1건(메타데이터·분류·관계)에서 rdflib 그래프 1개를 만든다. STEP 3 미리보기, STEP 6 검증, STEP 7 직렬화,
카탈로그 발행이 모두 이 함수의 출력을 쓴다 — 검증한 대상과 내보내는 대상이 같다는 것을 정본 체크섬으로 보증한다.

원칙
- 결측 필드는 트리플을 만들지 않는다 (빈 리터럴 금지).
- 참조와 정의는 항상 쌍으로 만든다 (참조된 IRI 는 같은 그래프 안에 타입 선언이 있다).
- 승인이 필요한 ARD 필수 필드는 사람이 승인하기 전까지 미입력으로 간주한다.
- 빈 노드를 쓰지 않는다 (체크섬·동형성 검사의 결정성 확보).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, OWL, PROV, RDF, RDFS, SKOS, XSD
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Organization, Process, ProcessDataset, Relation, TaxonomyAxis, TaxonomyCode
from . import minting

SPDX = Namespace("http://spdx.org/rdf/terms#")
RAI = Namespace("http://mlcommons.org/croissant/RAI/")
CSVW = Namespace("http://www.w3.org/ns/csvw#")
QB = Namespace("http://purl.org/linked-data/cube#")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
ADMS = Namespace("http://www.w3.org/ns/adms#")
DQV = Namespace("http://www.w3.org/ns/dqv#")
OA = Namespace("http://www.w3.org/ns/oa#")
LANG_NS = "http://id.loc.gov/vocabulary/iso639-1/"
IANA_MT = "https://www.iana.org/assignments/media-types/"

# 승인 전에는 정본에 반영하지 않는 필드
APPROVAL_FIELDS_DATASET = ["publisher_org_id", "media_type"]
APPROVAL_FIELDS_STREAM = ["publisher_org_id", "temporal_resolution", "event_time_column"]

# STEP 3 폼이 다루는 필드 정의 (프런트가 그대로 내려받아 폼을 그린다)
# level 은 가이드라인 표 9~12 의 우선순위(필수·권장·선택)를 따른다. 가이드라인에 없는 필드는 제품 기준이다.
# level 이 필수여도 비워 둘 수 있다 — 확정·발행을 막는 것은 승인 필드(approval)와 SHACL Violation 뿐이고,
# 나머지 결측은 STEP 8 진단에서 감점된다. guide 는 근거 위치다.
META_FIELDS: list[dict[str, Any]] = [
    {"name": "title", "property": "dcterms:title", "label": "데이터명", "level": "필수", "type": "text", "scope": "all", "guide": "표 9 데이터명"},
    {"name": "description", "property": "dcterms:description", "label": "데이터 설명", "level": "필수", "type": "textarea", "scope": "all", "guide": "표 9 데이터 설명"},
    {"name": "publisher_org_id", "property": "dcterms:publisher", "label": "제공기관", "level": "필수", "type": "org", "scope": "all", "approval": True, "guide": "표 9 제공기관"},
    {"name": "media_type", "property": "dcat:mediaType", "label": "데이터셋 유형 (IANA 미디어타입)", "level": "필수", "type": "media_type", "scope": "dataset", "approval": True, "guide": "표 9 데이터셋 유형"},
    {"name": "temporal_resolution", "property": "dcat:temporalResolution", "label": "시간 해상도 (ISO 8601 duration)", "level": "필수", "type": "duration", "scope": "stream", "approval": True},
    {"name": "event_time_column", "property": "fde:eventTimeColumn", "label": "event-time 컬럼", "level": "필수", "type": "text", "scope": "stream", "approval": True},
    {"name": "creator", "property": "dcterms:creator", "label": "소관기관 (운영부서명)", "level": "필수", "type": "text", "scope": "all", "guide": "표 9 소관기관"},
    {"name": "references", "property": "dcterms:references", "label": "관련법령 (법적 근거·URL)", "level": "필수", "type": "tags", "scope": "all", "guide": "표 9 관련법령"},
    {"name": "landing_page", "property": "dcat:landingPage", "label": "제공시스템 (안내 웹 페이지)", "level": "필수", "type": "url", "scope": "all", "guide": "표 9 제공시스템"},
    {"name": "access_url", "property": "dcat:accessURL", "label": "접속 URL (배포본)", "level": "필수", "type": "url", "scope": "dataset", "guide": "표 9 접속 URL"},
    {"name": "accrual_periodicity", "property": "dcterms:accrualPeriodicity", "label": "갱신주기", "level": "필수", "type": "periodicity", "scope": "dataset", "guide": "표 9 갱신주기"},
    {"name": "keywords", "property": "dcat:keyword", "label": "키워드", "level": "필수", "type": "tags", "scope": "all", "guide": "표 9 키워드"},
    {"name": "language", "property": "dcterms:language", "label": "언어 (ISO 639-1)", "level": "필수", "type": "text", "scope": "all", "guide": "표 9 언어"},
    {"name": "contact_name", "property": "dcat:contactPoint / vcard:fn", "label": "담당 부서·담당자", "level": "필수", "type": "text", "scope": "all", "guide": "표 9 담당자연락처"},
    {"name": "contact_email", "property": "dcat:contactPoint / vcard:hasEmail", "label": "담당 이메일", "level": "필수", "type": "text", "scope": "all", "guide": "표 9 담당자연락처"},
    {"name": "contact_phone", "property": "dcat:contactPoint / vcard:hasTelephone", "label": "담당 전화번호", "level": "선택", "type": "text", "scope": "all", "guide": "표 9 담당자연락처"},
    {"name": "version", "property": "owl:versionInfo", "label": "버전", "level": "필수", "type": "text", "scope": "all", "guide": "표 10 버전"},
    {"name": "issued", "property": "dcterms:issued", "label": "등록일시 (최초 등록일)", "level": "필수", "type": "date", "scope": "all", "guide": "표 10 등록일시"},
    {"name": "modified", "property": "dcterms:modified", "label": "수정일시 (마지막 수정일)", "level": "필수", "type": "date", "scope": "all", "guide": "표 10 수정일시"},
    {"name": "version_notes", "property": "adms:versionNotes", "label": "버전 노트 (이전 버전 대비 변경 사항)", "level": "필수", "type": "textarea", "scope": "all", "guide": "표 10 버전 노트"},
    {"name": "rights", "property": "dcterms:rights", "label": "저작권 (저작자 표시·영리 이용·변경 허용 여부)", "level": "필수", "type": "textarea", "scope": "all", "guide": "표 11 저작권"},
    {"name": "temporal_start", "property": "dcterms:temporal / dcat:startDate", "label": "시간범위 시작", "level": "권장", "type": "date", "scope": "dataset", "guide": "표 9 시간범위"},
    {"name": "temporal_end", "property": "dcterms:temporal / dcat:endDate", "label": "시간범위 종료", "level": "권장", "type": "date", "scope": "dataset", "guide": "표 9 시간범위"},
    {"name": "spatial", "property": "dcterms:spatial", "label": "공간범위", "level": "권장", "type": "text", "scope": "all", "guide": "표 9 공간범위"},
    {"name": "endpoint_url", "property": "dcat:endpointURL", "label": "API 엔드포인트 URL", "level": "권장", "type": "url", "scope": "all", "guide": "부록 3 데이터 제공"},
    {"name": "provenance", "property": "dcterms:provenance", "label": "출처·가공 이력 (원천 시스템·수집 방식·정제·비식별 처리)", "level": "권장", "type": "textarea", "scope": "all", "guide": "부록 3 품질 및 이력"},
    {"name": "rai_data_biases", "property": "rai:dataBiases", "label": "데이터 편향성 (확인된 편향 유형)", "level": "권장", "type": "textarea", "scope": "all", "guide": "표 12 데이터 편향성"},
    {"name": "timezone", "property": "fde:timezone", "label": "타임존", "level": "권장", "type": "text", "scope": "stream"},
    {"name": "watermark", "property": "fde:watermarkDelay", "label": "워터마크 지연 허용", "level": "권장", "type": "duration", "scope": "stream"},
    {"name": "quality_annotation", "property": "dqv:hasQualityAnnotation", "label": "품질 검증 정보 (수행한 품질 검토·평가 내용)", "level": "선택", "type": "textarea", "scope": "all", "guide": "표 12 품질 검증 정보"},
    {"name": "rai_known_limitations", "property": "rai:knownLimitations", "label": "데이터 한계 (제한사항·해석 시 유의 사항)", "level": "선택", "type": "textarea", "scope": "all", "guide": "표 12 데이터 한계"},
    {"name": "rai_missing_data", "property": "rai:dataCollectionMissingData", "label": "결측치 정보 (비율·발생 사유·처리 방식)", "level": "선택", "type": "textarea", "scope": "all", "guide": "표 12 결측치 정보"},
    {"name": "conforms_to", "property": "dcterms:conformsTo", "label": "준수 표준 (날짜 형식·코드 체계·좌표계 등)", "level": "선택", "type": "tags", "scope": "all", "guide": "부록 3 의미 및 표준"},
    {"name": "late_policy", "property": "fde:lateDataPolicy", "label": "지각(late) 데이터 정책", "level": "선택", "type": "late_policy", "scope": "stream"},
    {"name": "role_note", "property": "rdfs:comment", "label": "역할 설명 (문장화에 사용)", "level": "선택", "type": "text", "scope": "all"},
]
META_FIELD_NAMES = {f["name"] for f in META_FIELDS}
_DURATION = re.compile(r"^P(?!$)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def is_duration(v: str) -> bool:
    return bool(_DURATION.match(v or ""))


@dataclass
class Canonical:
    graph: Graph
    resource_id: str
    iri: str
    minted: bool
    is_stream: bool
    checksum: str
    readiness: dict[str, Any]
    record: dict[str, Any] = field(default_factory=dict)


def new_graph() -> Graph:
    g = Graph()
    s = get_settings()
    for prefix, ns in (("dcat", DCAT), ("dcterms", DCTERMS), ("prov", PROV), ("foaf", FOAF), ("skos", SKOS),
                       ("xsd", XSD), ("rdfs", RDFS), ("spdx", SPDX), ("rai", RAI), ("csvw", CSVW), ("qb", QB),
                       ("vcard", VCARD), ("owl", OWL), ("adms", ADMS), ("dqv", DQV), ("oa", OA),
                       ("fde", Namespace(s.def_ns))):
        g.bind(prefix, ns, override=True, replace=True)
    return g


def fde() -> Namespace:
    return Namespace(get_settings().def_ns)


def graph_checksum(g: Graph) -> str:
    """정본 체크섬: 정렬한 N-Triples 의 SHA-256. 빈 노드가 없으므로 결정적이다."""
    lines = sorted(line for line in g.serialize(format="nt").splitlines() if line.strip())
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def effective_meta(pd: ProcessDataset) -> dict[str, Any]:
    """승인 규칙을 적용한 메타데이터. 승인 대상 필드는 approved_fields 에 있을 때만 값이 살아남는다."""
    meta = dict(pd.meta or {})
    needs = APPROVAL_FIELDS_STREAM if pd.asset.kind == "stream" else APPROVAL_FIELDS_DATASET
    approved = set(pd.approved_fields or [])
    for f in needs:
        if f not in approved:
            meta.pop(f, None)
    return {k: v for k, v in meta.items() if v not in (None, "", [], {})}


_IRI_UNSAFE = re.compile(r'[\s<>"{}|\\^`]')


def _iri(v: Any) -> URIRef:
    """사용자가 적은 주소를 IRI 로 만든다. Turtle 로 쓸 수 없는 문자(공백·중괄호 등)는 퍼센트 인코딩한다 (한글은 그대로 둔다)."""
    return URIRef(_IRI_UNSAFE.sub(lambda m: "".join(f"%{b:02X}" for b in m.group(0).encode("utf-8")), str(v).strip()))


def _lit(v: Any, lang: str | None = "ko") -> Literal:
    return Literal(str(v).strip(), lang=lang) if lang else Literal(str(v).strip())


def _date_lit(v: str) -> Literal:
    v = str(v).strip()
    if _DATETIME.match(v):
        return Literal(v, datatype=XSD.dateTime)
    if _DATE.match(v):
        return Literal(v, datatype=XSD.date)
    return Literal(v)


def _taxonomy_index(db: Session) -> dict[str, TaxonomyCode]:
    return {c.code: c for c in db.scalars(select(TaxonomyCode))}


def _add_concept(g: Graph, code: TaxonomyCode) -> URIRef:
    iri = URIRef(minting.concept_iri(code.code))
    g.add((iri, RDF.type, SKOS.Concept))
    g.add((iri, SKOS.prefLabel, _lit(code.label)))
    g.add((iri, SKOS.notation, Literal(code.code)))
    g.add((iri, SKOS.inScheme, URIRef(minting.scheme_iri(code.axis_code))))
    return iri


def _add_scheme_defs(g: Graph, db: Session) -> None:
    """참조된 개념의 스킴 노드를 타입과 함께 선언한다."""
    used = {str(o).rsplit("/", 1)[-1] for o in g.objects(None, SKOS.inScheme)}
    if not used:
        return
    for axis in db.scalars(select(TaxonomyAxis).where(TaxonomyAxis.code.in_(used))):
        s = URIRef(minting.scheme_iri(axis.code))
        g.add((s, RDF.type, SKOS.ConceptScheme))
        g.add((s, SKOS.prefLabel, _lit(f"{axis.code} {axis.name}")))


def build(db: Session, pd: ProcessDataset, mode: str = "draft") -> Canonical:
    FDE = fde()
    asset = pd.asset
    process: Process = pd.process
    is_stream = asset.kind == "stream"
    meta = effective_meta(pd)
    rid, minted = minting.resource_id(db, pd, mode)
    ds = URIRef(minting.resource_iri(rid))
    g = new_graph()
    codes = _taxonomy_index(db)
    record: dict[str, Any] = {"@id": str(ds), "identifier": rid}

    # ---- 타입
    types = [DCAT.Dataset] + ([DCAT.DataService] if is_stream else [])
    extra_type_map = {"prov:Entity": PROV.Entity, "qb:DataSet": QB.DataSet, "foaf:Document": FOAF.Document}
    for cls in pd.extra_classes or []:
        if cls in extra_type_map:
            types.append(extra_type_map[cls])
    for t in types:
        g.add((ds, RDF.type, t))
    record["type"] = [g.namespace_manager.normalizeUri(t) for t in types]
    g.add((ds, DCTERMS.identifier, Literal(rid)))

    # ---- 기본 기술
    title = meta.get("title")
    if title:
        g.add((ds, DCTERMS.title, _lit(title)))
        record["title"] = title
    if meta.get("description"):
        g.add((ds, DCTERMS.description, _lit(meta["description"])))
        record["description"] = meta["description"]
    if meta.get("role_note"):
        g.add((ds, RDFS.comment, _lit(meta["role_note"])))
        record["roleNote"] = meta["role_note"]
    for kw in meta.get("keywords", []) or []:
        if str(kw).strip():
            g.add((ds, DCAT.keyword, _lit(kw)))
    if meta.get("keywords"):
        record["keywords"] = [str(k).strip() for k in meta["keywords"] if str(k).strip()]
    if meta.get("language"):
        lang = str(meta["language"]).strip()
        if re.fullmatch(r"[A-Za-z]{2}", lang):
            # 가이드라인 표 9 예시대로 ISO 639-1 코드는 LoC 어휘 IRI 로 참조한다
            lang_iri = URIRef(LANG_NS + lang.lower())
            g.add((ds, DCTERMS.language, lang_iri))
            g.add((lang_iri, RDF.type, DCTERMS.LinguisticSystem))
        else:
            g.add((ds, DCTERMS.language, Literal(lang)))
        record["language"] = lang
    if meta.get("version"):
        ver = str(meta["version"]).strip()
        g.add((ds, URIRef(str(DCAT) + "version"), Literal(ver)))  # DCAT 3 용어 (rdflib 의 DCAT 정의에는 아직 없다)
        g.add((ds, OWL.versionInfo, Literal(ver)))  # 가이드라인 표 10 은 owl:versionInfo 로 적는다
        record["version"] = ver
    if meta.get("version_notes"):
        g.add((ds, ADMS.versionNotes, _lit(meta["version_notes"])))
        record["versionNotes"] = meta["version_notes"]
    if meta.get("creator"):
        creator = URIRef(f"{ds}#creator")
        g.add((ds, DCTERMS.creator, creator))
        g.add((creator, RDF.type, FOAF.Agent))
        g.add((creator, RDFS.label, _lit(meta["creator"])))
        g.add((creator, FOAF.name, _lit(meta["creator"])))
        record["creator"] = meta["creator"]
    if meta.get("landing_page"):
        page = _iri(meta["landing_page"])
        g.add((ds, DCAT.landingPage, page))
        g.add((page, RDF.type, FOAF.Document))
        record["landingPage"] = str(page)
    if meta.get("rights"):
        rights = URIRef(f"{ds}#rights")
        g.add((ds, DCTERMS.rights, rights))
        g.add((rights, RDF.type, DCTERMS.RightsStatement))
        g.add((rights, RDFS.label, _lit(meta["rights"])))
        record["rights"] = meta["rights"]
    for key, prop in (("issued", DCTERMS.issued), ("modified", DCTERMS.modified)):
        if meta.get(key):
            g.add((ds, prop, _date_lit(meta[key])))
            record[key] = meta[key]
    if meta.get("spatial"):
        g.add((ds, DCTERMS.spatial, _lit(meta["spatial"])))
        record["spatial"] = meta["spatial"]
    for std in meta.get("conforms_to", []) or []:
        std = str(std).strip()
        if std:
            g.add((ds, DCTERMS.conformsTo, _iri(std) if re.match(r"^https?://", std) else Literal(std)))
    if meta.get("conforms_to"):
        record["conformsTo"] = list(meta["conforms_to"])
    for ref in meta.get("references", []) or []:
        ref = str(ref).strip()
        if ref:
            g.add((ds, DCTERMS.references, _iri(ref) if re.match(r"^https?://", ref) else Literal(ref, lang="ko")))
    if meta.get("references"):
        record["references"] = list(meta["references"])
    if meta.get("rai_data_biases"):
        g.add((ds, RAI.dataBiases, _lit(meta["rai_data_biases"])))
        record["dataBiases"] = meta["rai_data_biases"]
    if meta.get("rai_known_limitations"):
        g.add((ds, RAI.knownLimitations, _lit(meta["rai_known_limitations"])))
        record["knownLimitations"] = meta["rai_known_limitations"]
    if meta.get("provenance"):
        prov_note = URIRef(f"{ds}#provenance")
        g.add((ds, DCTERMS.provenance, prov_note))
        g.add((prov_note, RDF.type, DCTERMS.ProvenanceStatement))
        g.add((prov_note, RDFS.label, _lit(meta["provenance"])))
        record["provenance"] = meta["provenance"]
    if meta.get("rai_missing_data"):
        g.add((ds, RAI.dataCollectionMissingData, _lit(meta["rai_missing_data"])))
        record["missingData"] = meta["rai_missing_data"]
    if meta.get("quality_annotation"):
        qa = URIRef(f"{ds}#quality-annotation")
        g.add((ds, DQV.hasQualityAnnotation, qa))
        g.add((qa, RDF.type, DQV.QualityAnnotation))
        g.add((qa, OA.hasTarget, ds))
        g.add((qa, OA.motivatedBy, DQV.qualityAssessment))
        g.add((qa, OA.bodyValue, _lit(meta["quality_annotation"])))
        record["qualityAnnotation"] = meta["quality_annotation"]
    if meta.get("temporal_start") or meta.get("temporal_end"):
        period = URIRef(f"{ds}#temporal")
        g.add((ds, DCTERMS.temporal, period))
        g.add((period, RDF.type, DCTERMS.PeriodOfTime))
        if meta.get("temporal_start"):
            g.add((period, DCAT.startDate, _date_lit(meta["temporal_start"])))
        if meta.get("temporal_end"):
            g.add((period, DCAT.endDate, _date_lit(meta["temporal_end"])))
        record["temporal"] = {k: meta[f"temporal_{k}"] for k in ("start", "end") if meta.get(f"temporal_{k}")}
    if meta.get("contact_name") or meta.get("contact_email") or meta.get("contact_phone"):
        contact = URIRef(f"{ds}#contact")
        g.add((ds, DCAT.contactPoint, contact))
        g.add((contact, RDF.type, VCARD.Kind))
        if meta.get("contact_name"):
            g.add((contact, VCARD.fn, _lit(meta["contact_name"])))
        if meta.get("contact_email"):
            g.add((contact, VCARD.hasEmail, URIRef("mailto:" + str(meta["contact_email"]).strip())))
        if meta.get("contact_phone"):
            g.add((contact, VCARD.hasTelephone, URIRef("tel:" + re.sub(r"[^0-9+-]", "", str(meta["contact_phone"])))))
        record["contactPoint"] = {k: meta[f"contact_{k}"] for k in ("name", "email", "phone") if meta.get(f"contact_{k}")}

    # ---- 제공기관 (승인 필수)
    org: Organization | None = db.get(Organization, int(meta["publisher_org_id"])) if meta.get("publisher_org_id") else None
    if org:
        o = URIRef(minting.org_iri(org.code))
        g.add((ds, DCTERMS.publisher, o))
        g.add((o, RDF.type, FOAF.Agent))
        g.add((o, RDF.type, PROV.Organization))
        g.add((o, RDFS.label, _lit(org.label)))
        g.add((ds, PROV.wasAttributedTo, o))
        record["publisher"] = {"@id": str(o), "label": org.label}

    # ---- 배포본 (파일형, mediaType 승인 필수)
    media_type = meta.get("media_type")
    if not is_stream and media_type:
        dist = URIRef(minting.distribution_iri(rid, asset.ext))
        g.add((ds, DCAT.distribution, dist))
        g.add((dist, RDF.type, DCAT.Distribution))
        g.add((dist, DCAT.mediaType, URIRef(IANA_MT + media_type)))
        d_rec: dict[str, Any] = {"@id": str(dist), "mediaType": media_type}
        form = _form_label(media_type, asset.data_form)
        if form:
            g.add((dist, DCTERMS["format"], _lit(form)))
            d_rec["format"] = form
        if asset.filename:
            g.add((dist, DCTERMS.title, _lit(asset.filename)))
        if asset.size:
            g.add((dist, DCAT.byteSize, Literal(asset.size, datatype=XSD.nonNegativeInteger)))
            d_rec["byteSize"] = asset.size
        if asset.sha256:
            cs = URIRef(f"{dist}#checksum")
            g.add((dist, SPDX.checksum, cs))
            g.add((cs, RDF.type, SPDX.Checksum))
            g.add((cs, SPDX.algorithm, SPDX.checksumAlgorithm_sha256))
            g.add((cs, SPDX.checksumValue, Literal(asset.sha256, datatype=XSD.hexBinary)))
            d_rec["checksum"] = {"algorithm": "sha256", "value": asset.sha256}
        if meta.get("access_url"):
            g.add((dist, DCAT.accessURL, _iri(meta["access_url"])))
            d_rec["accessURL"] = meta["access_url"]
        if meta.get("endpoint_url"):
            # 파일과 함께 API 로도 제공하는 경우: 배포본이 접근 서비스를 가리킨다 (DCAT 3 dcat:accessService)
            svc = URIRef(f"{ds}#api")
            g.add((dist, DCAT.accessService, svc))
            g.add((svc, RDF.type, DCAT.DataService))
            g.add((svc, DCTERMS.title, _lit(f"{title or rid} API")))
            g.add((svc, DCAT.endpointURL, _iri(meta["endpoint_url"])))
            g.add((svc, DCAT.servesDataset, ds))
            d_rec["accessService"] = {"@id": str(svc), "endpointURL": meta["endpoint_url"]}
        if "csvw:Table" in (pd.extra_classes or []):
            _add_table_schema(g, dist, asset.profile)
        record["distribution"] = d_rec
    if not is_stream and meta.get("accrual_periodicity"):
        v = str(meta["accrual_periodicity"]).strip()
        g.add((ds, DCTERMS.accrualPeriodicity, Literal(v, datatype=XSD.duration) if is_duration(v) else Literal(v)))
        record["accrualPeriodicity"] = v

    # ---- 스트림 속성
    if is_stream:
        tr = meta.get("temporal_resolution")
        if tr:
            tr = str(tr).strip()
            g.add((ds, DCAT.temporalResolution, Literal(tr, datatype=XSD.duration) if is_duration(tr) else Literal(tr)))
            record["temporalResolution"] = tr
        if meta.get("event_time_column"):
            g.add((ds, FDE.eventTimeColumn, Literal(str(meta["event_time_column"]).strip())))
            record["eventTimeColumn"] = meta["event_time_column"]
        if meta.get("endpoint_url"):
            g.add((ds, DCAT.endpointURL, _iri(meta["endpoint_url"])))
            record["endpointURL"] = meta["endpoint_url"]
        if meta.get("timezone"):
            g.add((ds, FDE.timezone, Literal(str(meta["timezone"]).strip())))
            record["timezone"] = meta["timezone"]
        wm = meta.get("watermark")
        if wm:
            wm = str(wm).strip()
            g.add((ds, FDE.watermarkDelay, Literal(wm, datatype=XSD.duration) if is_duration(wm) else Literal(wm)))
            record["watermarkDelay"] = wm
        if meta.get("late_policy"):
            g.add((ds, FDE.lateDataPolicy, _lit(meta["late_policy"])))
            record["lateDataPolicy"] = meta["late_policy"]

    # ---- 분류 (STEP 4)
    cls = pd.classification or {}
    axis_prop = {"F1": DCAT.theme, "F2": DCTERMS.type, "F3": FDE.granularity, "F5": FDE.aiPurpose,
                 "F6": FDE.governanceMode}
    rec_key = {"F1": "theme", "F2": "dataType", "F3": "granularity", "F5": "aiPurpose", "F6": "governance"}
    for axis, prop in axis_prop.items():
        labels = []
        for code in _as_list(cls.get(axis)):
            tc = codes.get(code)
            if tc and tc.active:
                g.add((ds, prop, _add_concept(g, tc)))
                labels.append(tc.label)
                if axis == "F3" and not is_stream:
                    meters = (tc.extra or {}).get("meters")
                    if meters:
                        g.add((ds, DCAT.spatialResolutionInMeters, Literal(meters, datatype=XSD.decimal)))
        if labels:
            record[rec_key[axis]] = labels
    for code in _as_list(cls.get("F4")):
        tc = codes.get(code)
        if tc and tc.active:
            prop = DCTERMS.license if (tc.extra or {}).get("property") == "dcterms:license" else DCTERMS.accessRights
            c = _add_concept(g, tc)
            g.add((ds, prop, c))
            g.add((c, RDF.type, DCTERMS.LicenseDocument if prop == DCTERMS.license else DCTERMS.RightsStatement))
            record["license" if prop == DCTERMS.license else "accessRights"] = tc.label
    n2sf = cls.get("N2SF")
    if n2sf and n2sf in codes:
        g.add((ds, FDE.n2sfGrade, _add_concept(g, codes[n2sf])))
        record["n2sfGrade"] = n2sf.replace("N2SF-", "")
    keys_rec = []
    for k in cls.get("K") or []:
        tc = codes.get(k.get("code", ""))
        if not tc:
            continue
        node = URIRef(f"{ds}#key-{tc.code}")
        g.add((ds, FDE.joinKey, node))
        g.add((node, RDF.type, FDE.JoinKeyBinding))
        g.add((node, FDE.keyConcept, _add_concept(g, tc)))
        item = {"key": tc.code, "label": tc.label}
        if k.get("column"):
            g.add((node, FDE.mappedColumn, Literal(str(k["column"]))))
            item["column"] = k["column"]
        if k.get("table"):
            g.add((node, FDE.mappedTable, Literal(str(k["table"]))))
            item["table"] = k["table"]
        keys_rec.append(item)
    if keys_rec:
        record["joinKeys"] = keys_rec

    # ---- 조합 (prov:Collection)
    if process.combo_title and pd.in_combo:
        col = URIRef(minting.collection_iri(process, mode))
        g.add((ds, DCTERMS.isPartOf, col))
        g.add((col, RDF.type, PROV.Collection))
        g.add((col, DCTERMS.title, _lit(process.combo_title)))
        if process.combo_description:
            g.add((col, DCTERMS.description, _lit(process.combo_description)))
        g.add((col, PROV.hadMember, ds))
        record["isPartOf"] = {"@id": str(col), "title": process.combo_title}

    # ---- 관계 (STEP 5)
    rels_rec = []
    rels = db.scalars(select(Relation).where(Relation.process_id == process.id,
                                             (Relation.source_id == pd.id) | (Relation.target_id == pd.id),
                                             Relation.status == "confirmed").order_by(Relation.priority, Relation.id))
    for rel in rels:
        outgoing = rel.source_id == pd.id
        other = rel.target if outgoing else rel.source
        if not other.in_combo:
            continue
        other_rid, _ = minting.resource_id(db, other, mode)
        o = URIRef(minting.resource_iri(other_rid))
        other_title = (other.meta or {}).get("title") or other.asset.name
        g.add((o, RDF.type, DCAT.Resource))
        g.add((o, DCTERMS.title, _lit(other_title)))
        if rel.type == "DERIVED_FROM":
            if outgoing:
                g.add((ds, PROV.wasDerivedFrom, o))
                g.add((ds, DCTERMS.relation, o))
                rels_rec.append({"type": "WAS_DERIVED_FROM", "target": other_title, "direction": "out"})
            else:
                g.add((ds, DCTERMS.relation, o))
                rels_rec.append({"type": "WAS_DERIVED_FROM", "target": other_title, "direction": "in"})
            continue
        if not outgoing:
            # 역방향은 단순 관계로만 남긴다 (한정 관계 노드는 출발 쪽 데이터셋이 소유)
            g.add((ds, DCTERMS.relation, o))
            rels_rec.append({"type": rel.type, "target": other_title, "direction": "in",
                             **({"key": rel.key_code} if rel.key_code else {})})
            continue
        r = URIRef(minting.relation_iri(rel.id))
        g.add((ds, DCTERMS.relation, o))  # 가이드라인 표 9 연계데이터셋 — 한정 관계와 함께 단순 관계도 남긴다
        g.add((ds, DCAT.qualifiedRelation, r))
        g.add((r, RDF.type, DCAT.Relationship))
        g.add((r, DCTERMS.relation, o))
        role = URIRef(f"{minting.def_ns()}role/{'joinedOn' if rel.type == 'JOINED_ON' else 'groupedWith'}")
        g.add((r, DCAT.hadRole, role))
        g.add((role, RDF.type, DCAT.Role))
        g.add((role, SKOS.prefLabel, Literal(rel.type)))
        item: dict[str, Any] = {"type": rel.type, "target": other_title, "direction": "out"}
        if rel.type == "JOINED_ON":
            g.add((r, FDE.ssotPriority, Literal(rel.priority, datatype=XSD.integer)))
            item["ssotPriority"] = rel.priority
            if rel.key_code and rel.key_code in codes:
                g.add((r, FDE.keyConcept, _add_concept(g, codes[rel.key_code])))
                item["key"] = rel.key_code
            if rel.source_column:
                g.add((r, FDE.sourceColumn, Literal(rel.source_column)))
                item["sourceColumn"] = rel.source_column
            if rel.target_column:
                g.add((r, FDE.targetColumn, Literal(rel.target_column)))
                item["targetColumn"] = rel.target_column
            rate = (rel.stats or {}).get("source_match_rate")
            if rate is not None:
                g.add((r, FDE.matchRate, Literal(round(float(rate), 4), datatype=XSD.decimal)))
                item["matchRate"] = round(float(rate), 4)
        rels_rec.append(item)
    if rels_rec:
        record["relations"] = rels_rec

    # ---- 프로버넌스
    act = pd.authoring_activity
    if act:
        a = URIRef(minting.activity_iri(act.code))
        g.add((ds, PROV.wasGeneratedBy, a))
        g.add((a, RDF.type, PROV.Activity))
        g.add((a, RDFS.label, _lit(act.text)))
        g.add((a, PROV.startedAtTime, Literal(act.started_at.replace(microsecond=0).isoformat(), datatype=XSD.dateTime)))
        agent = URIRef(minting.agent_iri())
        g.add((a, PROV.wasAssociatedWith, agent))
        g.add((agent, RDF.type, PROV.SoftwareAgent))
        g.add((agent, RDFS.label, _lit("FDE Data Studio")))
        record["wasGeneratedBy"] = {"@id": str(a), "label": act.text}

    if "dcat:CatalogRecord" in (pd.extra_classes or []):
        rec_node = URIRef(f"{minting.id_ns()}record/{rid}")
        g.add((rec_node, RDF.type, DCAT.CatalogRecord))
        g.add((rec_node, FOAF.primaryTopic, ds))
        g.add((rec_node, DCTERMS.issued, Literal(pd.created_at.replace(microsecond=0).isoformat(), datatype=XSD.dateTime)))
        if pd.meta_confirmed_at:
            g.add((rec_node, DCTERMS.modified,
                   Literal(pd.meta_confirmed_at.replace(microsecond=0).isoformat(), datatype=XSD.dateTime)))

    _add_scheme_defs(g, db)

    required = ["title", "publisher", "temporalResolution", "eventTimeColumn"] if is_stream else ["title", "publisher", "distribution"]
    missing = [k for k in required if k not in record]
    recommended = ["description", "keywords", "theme", "dataType", "joinKeys", "n2sfGrade"]
    rec_missing = [k for k in recommended if k not in record]
    if "license" not in record and "accessRights" not in record:
        rec_missing.append("license")
    readiness = {"required": required, "missing": missing, "recommended_missing": rec_missing,
                 "level": "ai-ready" if not missing else "draft"}
    record["readiness"] = {"level": readiness["level"], "missing": missing}
    return Canonical(graph=g, resource_id=rid, iri=str(ds), minted=minted, is_stream=is_stream,
                     checksum=graph_checksum(g), readiness=readiness, record=record)


def _as_list(v: Any) -> list[str]:
    if v is None or v == "":
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _form_label(media_type: str, data_form: str | None) -> str | None:
    from .reference import vocab

    for mt in vocab()["media_types"]:
        if mt["value"] == media_type:
            return mt["form"]
    return data_form


def _add_table_schema(g: Graph, dist: URIRef, profile: dict[str, Any]) -> None:
    """csvw:Table 선택 시 프로파일된 컬럼 구조를 CSVW 로 기술한다."""
    type_map = {"integer": XSD.integer, "number": XSD.decimal, "datetime": XSD.dateTime, "boolean": XSD.boolean,
                "string": XSD.string}
    for ti, table in enumerate(profile.get("tables", []), start=1):
        t = URIRef(f"{dist}#table-{ti}")
        schema = URIRef(f"{dist}#table-{ti}-schema")
        g.add((dist, CSVW.table, t))
        g.add((t, RDF.type, CSVW.Table))
        g.add((t, DCTERMS.title, _lit(table["name"])))
        g.add((t, CSVW.tableSchema, schema))
        g.add((schema, RDF.type, CSVW.Schema))
        for ci, col in enumerate(table.get("columns", []), start=1):
            c = URIRef(f"{dist}#table-{ti}-col-{ci}")
            g.add((schema, CSVW.column, c))
            g.add((c, RDF.type, CSVW.Column))
            g.add((c, CSVW.name, Literal(col["name"])))
            g.add((c, CSVW.datatype, type_map.get(col["type"], XSD.string)))
            g.add((c, CSVW.required, Literal(col["null_rate"] == 0)))
