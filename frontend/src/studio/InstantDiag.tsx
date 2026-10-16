// STEP 3·4 오른쪽 '즉시 진단' — 저장할 때마다 STEP 8 규칙을 지금 정본으로 돌려 이 데이터셋에서 고칠 항목과 변화를 보인다. 기록은 남기지 않는다.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { DiagPreviewItem, DiagStatus } from "../types";
import { Badge, Card, QueryState, cx } from "../ui";
import { useStudio } from "./context";

const ST: Record<DiagStatus, { label: string; tone: "ok" | "warn" | "err" | "info" | "muted" }> = {
  met: { label: "충족", tone: "ok" },
  partial: { label: "부분", tone: "warn" },
  unmet: { label: "미흡", tone: "err" },
  pending: { label: "확인 대기", tone: "info" },
  na: { label: "해당 없음", tone: "muted" },
};

export function InstantDiag({ did, step, onFocus }: { did: number; step: number; onFocus?: (name: string) => void }) {
  const { pid, go } = useStudio();
  const q = useQuery({ queryKey: ["process", pid, "dataset", did, "diagnosis-preview"], queryFn: () => api.diagnosisPreview(did) });
  const [showAll, setShowAll] = useState(false);
  const p = q.data;
  const st = (i: DiagPreviewItem) => i.dataset_status ?? i.status;
  const todo = (p?.items || []).filter((i) => ["unmet", "partial", "pending"].includes(st(i)) && i.method !== "AUTO-DERIVED");
  const here = todo.filter((i) => i.route?.step === step);
  const elsewhere = todo.filter((i) => i.route?.step !== step);
  const pct = p && p.max_score > 0 ? Math.round((p.score / p.max_score) * 100) : null;
  const lastPct = p?.last_run && p.last_run.max_score > 0 ? Math.round((p.last_run.score / p.last_run.max_score) * 100) : null;
  const jump = (i: DiagPreviewItem) => {
    if (i.route?.step === step && i.focus && onFocus) onFocus(i.focus);
    else if (i.route) go(i.route.step, { dataset: did, focus: i.focus, fix: i.id });
  };
  const Row = ({ i }: { i: DiagPreviewItem }) => (
    <button type="button" className={cx("idiag-row", i.changed && "changed")} onClick={() => jump(i)} title={i.detail || undefined}>
      <span className="mono">{i.id}</span>
      <span className="grow ellipsis">{i.name}</span>
      {i.changed && i.previous && <span className="idiag-prev">{ST[i.previous].label} →</span>}
      <Badge tone={ST[st(i)].tone}>{ST[st(i)].label}</Badge>
      {i.provisional && <span className="idiag-prov" title="STEP 7 변환 뒤 확정">잠정</span>}
      {i.route && i.route.step !== step && <span className="tiny muted">S{i.route.step}</span>}
    </button>
  );
  return (
    <Card
      title={
        <>
          즉시 진단{" "}
          {p && (
            <Badge tone={pct !== null && pct >= 70 ? "ok" : pct !== null && pct >= 40 ? "warn" : "err"}>
              {pct}%{lastPct !== null && lastPct !== pct ? ` (저장된 진단 ${lastPct}%)` : ""}
            </Badge>
          )}
        </>
      }
      right={q.isFetching && !q.isLoading ? <span className="tiny muted"><span className="spinner" /> 다시 판정 중</span> : undefined}
    >
      <QueryState q={q}>
        {p && (
          <div className="col gap-8">
            <div className="small muted">
              지금 저장된 값으로 STEP 8 규칙을 돌린 결과입니다 (기록 없음). 이 데이터셋에 해당하는 {p.items.length}항목 중 충족 {p.counts.met} · 부분 {p.counts.partial} · 미흡 {p.counts.unmet} · 확인 대기 {p.counts.pending}
              {p.provisional_note && <span className="t-warn"> · {p.provisional_note}</span>}
            </div>
            {(p.improved.length > 0 || p.regressed.length > 0) && (
              <div className="idiag-delta">
                {p.improved.length > 0 && <span className="t-ok">▲ 개선 {p.improved.map((i) => i.id).join(", ")}</span>}
                {p.regressed.length > 0 && <span className="t-err">▼ 후퇴 {p.regressed.map((i) => i.id).join(", ")}</span>}
              </div>
            )}
            {here.length > 0 ? (
              <div>
                <div className="idiag-h">이 화면에서 고칠 항목 {here.length}</div>
                <div className="col gap-4">{here.map((i) => <Row key={i.id} i={i} />)}</div>
              </div>
            ) : (
              <div className="small t-ok">이 화면에서 고칠 항목이 없습니다.</div>
            )}
            {elsewhere.length > 0 && (
              <div>
                <button type="button" className="link-btn small" onClick={() => setShowAll((v) => !v)}>
                  {showAll ? "다른 단계 항목 접기" : `다른 단계에서 고칠 항목 ${elsewhere.length} 보기`}
                </button>
                {showAll && <div className="col gap-4 mt-4">{elsewhere.map((i) => <Row key={i.id} i={i} />)}</div>}
              </div>
            )}
          </div>
        )}
      </QueryState>
    </Card>
  );
}
