// 분류체계 세트 (v0.20) — 프로세스의 세트 고르기 · 복제해서 커스텀 · 세트 만들기 모달
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { TaxonomySet } from "../types";
import { Badge, Banner, Button, Field, Modal, useToast } from "../ui";

/** 세트 만들기(복제 · 빈 세트). onCreated 에 새 세트를 넘긴다 */
export function TaxonomySetModal({ sets, defaultBaseId, onClose, onCreated }: { sets: TaxonomySet[]; defaultBaseId?: number | null; onClose: () => void; onCreated: (s: TaxonomySet) => void | Promise<void> }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [scope, setScope] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [baseId, setBaseId] = useState<string>(defaultBaseId ? String(defaultBaseId) : String(sets.find((s) => s.is_default)?.id ?? ""));
  const [empty, setEmpty] = useState(false);
  const [busy, setBusy] = useState(false);
  const base = sets.find((s) => String(s.id) === baseId);
  const save = async () => {
    setBusy(true);
    try {
      const s = await api.createTaxonomySet({ name: name.trim(), scope: scope.trim() || null, description: description.trim() || null, base_set_id: baseId ? Number(baseId) : null, slug: slug.trim() || null, empty });
      await qc.invalidateQueries({ queryKey: ["taxonomy-sets"] });
      await qc.invalidateQueries({ queryKey: ["taxonomy"] });
      toast.ok(`분류체계 세트 생성 — ${s.name}${!empty && base ? ` (「${base.name}」 복제, 코드 ${s.code_total}개)` : ""}`);
      await onCreated(s);
      onClose();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title="분류체계 세트 만들기"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>취소</Button>
          <Button variant="primary" busy={busy} disabled={!name.trim()} onClick={save}>
            만들기
          </Button>
        </>
      }
    >
      <Banner tone="info">
        비슷한 세트를 <b>복제</b>해서 시작하고, 기관에 맞게 코드를 더하거나 폐기하세요. 복제한 코드는 원본 코드와 연결되어 규칙 기반 추천이 그대로 동작합니다. K 연계키 · N²SF 등급은 공통이라 세트에 들어가지 않습니다.
      </Banner>
      <div className="grid c2 mt-12">
        <Field label="세트 이름" hint="예: 현대제철 분류체계, 서울시교육청 교육데이터 분류체계">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={120} />
        </Field>
        <Field label="기관 · 분야" hint="누가 쓰는 세트인지">
          <input className="input" value={scope} onChange={(e) => setScope(e.target.value)} maxLength={120} placeholder="예: 현대제철 · 제조" />
        </Field>
        <Field label="복제할 원본">
          <select className="select" value={baseId} onChange={(e) => setBaseId(e.target.value)} disabled={empty}>
            <option value="">— 없음 —</option>
            {sets.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.code_total}코드{s.is_default ? " · 기본" : ""})
              </option>
            ))}
          </select>
          <label className="check small mt-4">
            <input type="checkbox" checked={empty} onChange={(e) => setEmpty(e.target.checked)} /> 빈 세트로 시작 (코드를 CSV 로 가져오거나 직접 추가)
          </label>
        </Field>
        <Field label="코드 접두 (영문, 선택)" hint="코드가 F1-HS-01 처럼 만들어집니다. 비우면 자동">
          <input className="input mono" value={slug} onChange={(e) => setSlug(e.target.value.replace(/[^A-Za-z0-9-]/g, "").slice(0, 16))} placeholder="HS" />
        </Field>
      </div>
      <Field label="설명" style={{ marginTop: 8 }}>
        <textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="출처 · 적용 범위 · 버전 등" />
      </Field>
    </Modal>
  );
}

/** 프로세스의 분류체계 세트 선택 (STEP 1 · STEP 4). 분류를 확정한 데이터셋이 있으면 서버가 변경을 거부한다 */
export function TaxonomySetPicker({ pid, current, disabled, compact, onChanged }: { pid: number; current: { id: number; name: string; scope: string | null; is_default: boolean } | undefined; disabled?: boolean; compact?: boolean; onChanged: () => Promise<void> | void }) {
  const toast = useToast();
  const sets = useQuery({ queryKey: ["taxonomy-sets"], queryFn: api.taxonomySets });
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const change = async (id: number) => {
    if (!current || id === current.id) return;
    setBusy(true);
    try {
      await api.updateProcess(pid, { taxonomy_set_id: id });
      await onChanged();
      const s = sets.data?.items.find((x) => x.id === id);
      toast.ok(`분류체계 세트 — ${s?.name ?? id}`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const items = sets.data?.items || [];
  return (
    <div className={compact ? "row wrap gap-4" : "col gap-4"} style={{ alignItems: compact ? "center" : undefined }}>
      {!compact && <div className="small bold dim">분류체계 세트</div>}
      <div className="row gap-4 wrap" style={{ alignItems: "center" }}>
        <select className="select" style={{ width: compact ? 260 : "100%", maxWidth: 360 }} value={current?.id ?? ""} disabled={disabled || busy || !items.length} onChange={(e) => void change(Number(e.target.value))} aria-label="분류체계 세트">
          {items.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
              {s.scope ? ` · ${s.scope}` : ""} ({s.code_total}코드{s.is_default ? " · 기본" : ""})
            </option>
          ))}
        </select>
        {!disabled && (
          <Button size="sm" variant="outline" onClick={() => setOpen(true)} title="지금 세트를 복제해 이 프로세스용 커스텀 세트를 만듭니다">
            복제해서 커스텀
          </Button>
        )}
        <Link className="link-btn small" to="/admin?tab=taxonomy" title="세트 목록 · 코드 추가 · CSV 가져오기">
          세트 관리 →
        </Link>
      </div>
      {!compact && current && (
        <div className="tiny muted">
          {current.is_default && <Badge tone="muted">기본</Badge>} F1~F6 코드는 이 세트에서 고릅니다. STEP 4 에서 분류를 확정하면 세트를 바꿀 수 없습니다.
        </div>
      )}
      {open && sets.data && (
        <TaxonomySetModal
          sets={items}
          defaultBaseId={current?.id}
          onClose={() => setOpen(false)}
          onCreated={async (s) => {
            await change(s.id);
          }}
        />
      )}
    </div>
  );
}
