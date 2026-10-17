// STEP 3 — AI 초안 제안. 서술형 칸의 초안을 받아 담당자가 하나씩 검토·채택한다 (채택해도 저장 전까지는 폼의 미저장 변경일 뿐이다)
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { AiDraft, MetaField } from "../types";
import { Badge, Banner, Button, Modal, useToast } from "../ui";

export function useAiStatus(did?: number) {
  return useQuery({ queryKey: ["ai-status", did ?? 0], queryFn: () => api.aiStatus(did), staleTime: 60_000 });
}

/** 초안을 만들 수 있는 칸: 서술형(textarea) · 준수 표준(tags, 규칙) */
export function draftable(fields: MetaField[], aiFields: string[], ruleFields: string[]): MetaField[] {
  const ok = new Set([...aiFields, ...ruleFields]);
  return fields.filter((f) => ok.has(f.name));
}

const asText = (t: string | string[]) => (Array.isArray(t) ? t.join(", ") : t);

export function AiDraftButton(props: {
  did: number;
  fields: MetaField[];
  editable: boolean;
  valueOf: (f: MetaField) => string | string[];
  onAdopt: (name: string, value: string | string[]) => void;
  size?: "sm" | "md";
  label?: string;
}) {
  const st = useAiStatus(props.did);
  const [open, setOpen] = useState(false);
  const enabled = st.data?.enabled ?? false;
  const blocked = st.data?.blocked_reason || null;
  const targets = st.data ? draftable(props.fields, st.data.fields, st.data.rule_fields) : [];
  if (!props.editable || targets.length === 0) return null;
  const title = blocked ? blocked : enabled ? `${st.data?.model} 로 서술형 칸 ${targets.length}개의 초안을 받습니다` : "AI 초안 기능이 꺼져 있습니다 (.env 의 FDE_ANTHROPIC_API_KEY)";
  return (
    <>
      <Button size={props.size || "sm"} variant={enabled && !blocked ? "outline" : "default"} disabled={!enabled || !!blocked} title={title} onClick={() => setOpen(true)}>
        ✦ {props.label || "AI 초안 제안"}
        {blocked && <Badge tone="err">제외</Badge>}
      </Button>
      {open && <DraftModal {...props} targets={targets} model={st.data?.model || ""} onClose={() => setOpen(false)} />}
    </>
  );
}

function DraftModal(props: {
  did: number;
  targets: MetaField[];
  model: string;
  valueOf: (f: MetaField) => string | string[];
  onAdopt: (name: string, value: string | string[]) => void;
  onClose: () => void;
}) {
  const toast = useToast();
  const empty = (f: MetaField) => {
    const v = props.valueOf(f);
    return Array.isArray(v) ? v.length === 0 : v.trim() === "";
  };
  const [picked, setPicked] = useState<Set<string>>(new Set(props.targets.filter(empty).map((f) => f.name)));
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ drafts: Record<string, AiDraft>; model: string | null; pii: number } | null>(null);
  const [adopt, setAdopt] = useState<Set<string>>(new Set());
  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, k: string) => {
    const next = new Set(set);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    setter(next);
  };
  const run = async () => {
    setBusy(true);
    try {
      const r = await api.aiDrafts(props.did, [...picked], instructions);
      setResult({ drafts: r.drafts, model: r.model, pii: r.pii_withheld || 0 });
      setAdopt(new Set(Object.keys(r.drafts)));
      if (Object.keys(r.drafts).length === 0) toast.error("초안을 받지 못했습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const apply = () => {
    let n = 0;
    for (const [name, d] of Object.entries(result?.drafts || {})) {
      if (!adopt.has(name)) continue;
      const f = props.targets.find((x) => x.name === name);
      if (!f) continue;
      props.onAdopt(name, f.type === "tags" ? (Array.isArray(d.text) ? d.text : d.text.split(",").map((s) => s.trim()).filter(Boolean)) : asText(d.text));
      n += 1;
    }
    toast.ok(`초안 ${n}개를 입력란에 넣었습니다 — 검토한 뒤 [변경 사항 저장] 을 눌러야 정본에 반영됩니다`);
    props.onClose();
  };
  const byName = new Map(props.targets.map((f) => [f.name, f]));

  return (
    <Modal
      title={<>✦ AI 초안 제안 <Badge tone="purple">{props.model}</Badge></>}
      onClose={props.onClose}
      wide
      footer={
        result ? (
          <>
            <Button onClick={() => setResult(null)}>다시 고르기</Button>
            <Button variant="primary" disabled={adopt.size === 0} onClick={apply}>
              선택한 {adopt.size}개 입력란에 넣기
            </Button>
          </>
        ) : (
          <>
            <Button onClick={props.onClose}>취소</Button>
            <Button variant="primary" busy={busy} disabled={picked.size === 0} onClick={run}>
              초안 받기 ({picked.size}개 칸)
            </Button>
          </>
        )
      }
    >
      {!result ? (
        <div className="col gap-12">
          <Banner tone="info">
            데이터셋 요약 · 컬럼 통계 · 이미 적은 내용을 Claude 에 보내 초안을 받습니다. <b>개인정보 의심 컬럼의 값은 보내지 않습니다.</b> 초안은 제안일 뿐이라 입력란에 넣은 뒤 담당자가 검토해 저장해야 정본에 들어가고, 호출은 활동 로그에
            남습니다. 결측치 정보 · 준수 표준은 모델 없이 프로파일 통계로 채웁니다.
          </Banner>
          <div className="small bold dim">초안을 받을 칸 (비어 있는 칸이 기본으로 선택됩니다)</div>
          <div className="col gap-4">
            {props.targets.map((f) => (
              <label key={f.name} className="check">
                <input type="checkbox" checked={picked.has(f.name)} onChange={() => toggle(picked, setPicked, f.name)} />
                {f.label}
                {!empty(f) && <Badge tone="warn">이미 입력됨 — 덮어씁니다</Badge>}
              </label>
            ))}
          </div>
          <label className="field">
            <span className="label">모델에게 덧붙일 지시 (선택)</span>
            <textarea className="textarea" rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="예: 교통안전 정책 분석 관점으로, 각 칸 2문장 이내" />
          </label>
        </div>
      ) : (
        <div className="col gap-12">
          <div className="small dim">
            초안 {Object.keys(result.drafts).length}개
            {result.pii > 0 && <> · 개인정보 의심 컬럼 {result.pii}개의 값은 보내지 않았습니다</>}. 채택할 것만 남기고 입력란에 넣으세요. 넣은 뒤에도 고칠 수 있습니다.
          </div>
          {Object.entries(result.drafts).map(([name, d]) => {
            const f = byName.get(name);
            return (
              <div key={name} className="card tight flat">
                <label className="check bold">
                  <input type="checkbox" checked={adopt.has(name)} onChange={() => toggle(adopt, setAdopt, name)} />
                  {f?.label || name}
                  <Badge tone={d.source === "llm" ? "purple" : "info"}>{d.source === "llm" ? "AI 초안" : "통계 자동"}</Badge>
                </label>
                <div className="mt-4" style={{ whiteSpace: "pre-wrap" }}>
                  {asText(d.text)}
                </div>
                {d.basis && <div className="small muted mt-4">근거: {d.basis}</div>}
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}

/** STEP 3 상단: 이 데이터셋의 외부 AI 전송 상태와 담당자 제외 표시. C 등급은 자동 제외라 토글이 잠긴다. */
export function AiExclusionBox({ did, editable }: { did: number; editable: boolean }) {
  const st = useAiStatus(did);
  const qc = useQueryClient();
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  if (!st.data || !st.data.enabled) return null;
  const isC = st.data.grade === "C";
  const ex = st.data.excluded;
  const set = async (excluded: boolean) => {
    setBusy(true);
    try {
      await api.setAiExclusion(did, excluded, reason);
      await Promise.all([qc.invalidateQueries({ queryKey: ["ai-status", did] }), qc.invalidateQueries({ queryKey: ["process"] }), qc.invalidateQueries({ queryKey: ["catalog"] })]);
      toast.ok(excluded ? "외부 AI 전송 제외로 표시했습니다 — 이 데이터셋에는 AI 초안을 쓰지 않습니다" : "외부 AI 전송 제외를 해제했습니다");
      setReason("");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={"banner " + (isC || ex ? "warn" : "info")} style={{ alignItems: "center" }}>
      <div className="grow small">
        <b>외부 AI 전송</b>{" "}
        {isC ? (
          <>— <Badge tone="err">N²SF C(기밀)</Badge> STEP 4 에서 담당자가 C 등급으로 지정해 AI 초안을 쓰지 않습니다 (요약·통계도 기관 밖으로 보내지 않음).</>
        ) : ex ? (
          <>— <Badge tone="warn">담당자 제외</Badge> {ex.by} · {ex.at.slice(0, 16).replace("T", " ")}{ex.reason ? ` · ${ex.reason}` : ""}. AI 초안 제안이 잠겨 있습니다.</>
        ) : (
          <>— 허용 (N²SF {st.data.grade || "미지정"}). AI 초안을 받으면 데이터셋 요약·컬럼 통계가 Anthropic API 로 전송됩니다. 보내면 안 되는 자료면 제외로 표시하세요.</>
        )}
      </div>
      {editable && !isC && (
        ex ? (
          <Button size="sm" busy={busy} onClick={() => void set(false)}>제외 해제</Button>
        ) : (
          <div className="row">
            <input className="input" style={{ width: 200 }} placeholder="사유 (선택)" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
            <Button size="sm" variant="outline" busy={busy} onClick={() => void set(true)}>외부 AI 전송 제외</Button>
          </div>
        )
      )}
    </div>
  );
}
