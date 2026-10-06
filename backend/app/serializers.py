"""모델 → API 응답(dict) 변환."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import (Activity, Artifact, Asset, CatalogEntry, DiagnosisRun, MintRecord, Organization, Process,
                     ProcessDataset, SerializationRun, TaxonomyAxis, User, ValidationRun)
from .services import canonical, minting
from .services.profiling import human_size, profile_summary


def user_out(u: User) -> dict[str, Any]:
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "org_label": u.org_label,
            "email": u.email, "active": u.active, "created_at": u.created_at}


def org_out(o: Organization) -> dict[str, Any]:
    return {"id": o.id, "code": o.code, "label": o.label, "kind": o.kind, "note": o.note, "active": o.active,
            "iri": minting.org_iri(o.code)}


def axis_out(a: TaxonomyAxis) -> dict[str, Any]:
    return {"code": a.code, "name": a.name, "nature": a.nature, "multi": a.multi, "version": a.version,
            "rdf_property": a.rdf_property, "description": a.description,
            "scheme_iri": minting.scheme_iri(a.code),
            "codes": [{"id": c.id, "code": c.code, "label": c.label, "definition": c.definition, "active": c.active,
                       "extra": c.extra or {}, "iri": minting.concept_iri(c.code)} for c in a.codes]}


def asset_out(a: Asset, detail: bool = False) -> dict[str, Any]:
    prof = a.profile or {}
    tables = prof.get("tables", [])
    out: dict[str, Any] = {
        "id": a.id, "name": a.name, "kind": a.kind, "source": a.source, "filename": a.filename, "ext": a.ext,
        "size": a.size, "size_label": human_size(a.size) if a.kind == "dataset" else None, "sha256": a.sha256,
        "media_type": a.media_type, "data_form": a.data_form, "description": a.description,
        "org": org_out(a.org) if a.org else None, "stream": a.stream or {},
        "profile_status": prof.get("status"), "profile_summary": profile_summary(prof),
        "table_count": len(tables), "column_count": sum(len(t["columns"]) for t in tables),
        "row_count": sum(t.get("rows", 0) for t in tables),
        "warnings": prof.get("warnings", []), "error": prof.get("error"),
        "key_candidates": a.key_candidates or [],
        "keys": sorted({c["code"] for c in (a.key_candidates or []) if c["score"] >= 0.5}),
        "created_at": a.created_at,
    }
    if detail:
        out["profile"] = prof
    return out


def dataset_out(db: Session, pd: ProcessDataset, mode: str, light: bool = False) -> dict[str, Any]:
    a = pd.asset
    needs = canonical.APPROVAL_FIELDS_STREAM if a.kind == "stream" else canonical.APPROVAL_FIELDS_DATASET
    rid, minted = minting.resource_id(db, pd, mode)
    rec = minting.minted_record(db, pd.asset_id)
    out: dict[str, Any] = {
        "id": pd.id, "process_id": pd.process_id, "asset": asset_out(a), "selected": pd.selected, "in_combo": pd.in_combo,
        "position": pd.position, "title": (pd.meta or {}).get("title") or a.name, "kind": a.kind,
        "meta": pd.meta or {}, "approved_fields": pd.approved_fields or [], "approval_fields": needs,
        "extra_classes": pd.extra_classes or [], "meta_confirmed_at": pd.meta_confirmed_at,
        "classification": pd.classification or {}, "class_confirmed_at": pd.class_confirmed_at,
        "resource_id": rid, "minted": minted, "minted_id": rec.minted_id if rec else None,
        "draft_id": minting.draft_id(pd),
        "authoring_activity": pd.authoring_activity.code if pd.authoring_activity else None,
    }
    if not light and pd.in_combo:
        c = canonical.build(db, pd, mode)
        out["readiness"] = c.readiness
        out["checksum"] = c.checksum
        out["triple_count"] = len(c.graph)
        out["iri"] = c.iri
    return out


def process_out(p: Process) -> dict[str, Any]:
    return {"id": p.id, "name": p.name, "status": p.status, "current_step": p.current_step,
            "combo_title": p.combo_title, "combo_description": p.combo_description, "combo_source": p.combo_source,
            "combo_confirmed_at": p.combo_confirmed_at, "pub_mode": p.pub_mode,
            "lineage_waiver_reason": p.lineage_waiver_reason, "lineage_waived_at": p.lineage_waived_at,
            "dataset_count": len(p.combo), "selected_count": sum(1 for d in p.datasets if d.selected),
            "created_at": p.created_at, "updated_at": p.updated_at, "completed_at": p.completed_at,
            "trashed_at": p.trashed_at}


def activity_out(a: Activity) -> dict[str, Any]:
    return {"id": a.id, "code": a.code, "type": a.type, "text": a.text, "agent_type": a.agent_type,
            "actor": a.actor_label, "process_id": a.process_id, "dataset_id": a.dataset_id, "at": a.started_at,
            "iri": minting.activity_iri(a.code)}


def validation_out(vr: ValidationRun | None, with_report: bool = False) -> dict[str, Any] | None:
    if vr is None:
        return None
    return {
        "id": vr.id, "process_id": vr.process_id, "mode": vr.mode, "shapes_version": vr.shapes_version,
        "status": vr.status, "pass_count": vr.pass_count, "fail_count": vr.fail_count, "warning_count": vr.warning_count,
        "started_at": vr.started_at, "ended_at": vr.ended_at, "activity": vr.activity.code if vr.activity else None,
        "datasets": [{
            "dataset_id": r.dataset_id, "name": r.dataset_name, "resource_id": r.resource_id, "checksum": r.checksum,
            "gate0": r.gate0, "conforms": r.conforms, "passed": r.passed, "violation_count": r.violation_count,
            "warning_count": r.warning_count, "info_count": r.info_count, "results": r.results,
            "triple_count": r.triple_count, **({"report_ttl": r.report_ttl} if with_report else {}),
        } for r in vr.results],
    }


def artifact_out(a: Artifact) -> dict[str, Any]:
    return {"id": a.id, "dataset_id": a.dataset_id, "dataset_name": a.dataset_name, "fmt": a.fmt, "filename": a.filename,
            "media_type": a.media_type, "size": a.size, "size_label": human_size(a.size) if a.size > 1023 else f"{a.size} B",
            "sha256": a.sha256, "set_checksum": a.set_checksum}


def serialization_out(sr: SerializationRun | None) -> dict[str, Any] | None:
    if sr is None:
        return None
    return {"id": sr.id, "process_id": sr.process_id, "validation_run_id": sr.validation_run_id, "mode": sr.mode,
            "formats": sr.formats, "ok_count": sr.ok_count, "fail_count": sr.fail_count, "self_verify": sr.self_verify,
            "started_at": sr.started_at, "ended_at": sr.ended_at, "activity": sr.activity.code if sr.activity else None,
            "artifacts": [artifact_out(a) for a in sr.artifacts]}


def diagnosis_out(dr: DiagnosisRun | None) -> dict[str, Any] | None:
    if dr is None:
        return None
    return {"id": dr.id, "process_id": dr.process_id, "ruleset_version": dr.ruleset_version, "score": dr.score,
            "max_score": dr.max_score, "pct": round(dr.score / dr.max_score * 100) if dr.max_score else 0,
            "summary": dr.summary, "items": dr.items, "started_at": dr.started_at, "ended_at": dr.ended_at,
            "activity": dr.activity.code if dr.activity else None}


def mint_out(m: MintRecord) -> dict[str, Any]:
    return {"id": m.id, "kind": m.kind, "minted_id": m.minted_id, "iri": minting.resource_iri(m.minted_id),
            "asset_id": m.asset_id, "asset_name": m.asset.name if m.asset else None, "process_id": m.process_id,
            "minted_at": m.minted_at, "note": m.note}


def catalog_out(e: CatalogEntry, detail: bool = False) -> dict[str, Any]:
    out = {"resource_id": e.resource_id, "iri": e.iri, "kind": e.kind, "title": e.title, "description": e.description,
           "publisher": e.publisher_label, "process_id": e.process_id, "process_name": e.process_name,
           "collection_title": e.collection_title, "version": e.version, "status": e.status, "checksum": e.checksum,
           "facets": e.facets or {}, "published_by": e.published_label, "published_at": e.published_at}
    if detail:
        out.update({"turtle": e.turtle, "jsonld": e.jsonld, "text_summary": e.text_summary, "schema_json": e.schema_json})
    return out
