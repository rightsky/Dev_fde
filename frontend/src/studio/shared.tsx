// 여러 STEP 이 함께 쓰는 부품
import type { ReactNode } from "react";
import type { Asset, Dataset, Gate0Check, TableProfile, ValidationRow } from "../types";
import { Badge, Button, KeyPill, SeverityBadge, cx, fmtNum, fmtPct } from "../ui";
import { useStudio } from "./context";

/** 단계 제목 줄 */
export function StepHeader({ n, title, sub, right, badge }: { n: number; title: string; sub?: ReactNode; right?: ReactNode; badge?: ReactNode }) {
  return (
    <div className="row between top wrap" style={{ marginBottom: 2 }}>
      <div>
        <h1 className="page-title">
          STEP {n}: {title} {badge}
        </h1>
        {sub && <p className="page-sub">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

/** 좌측 데이터셋 선택 목록. status 로 각 행의 상태 배지를 만든다. */
export function DatasetList(props: {
  datasets: Dataset[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  status?: (d: Dataset) => ReactNode;
  title?: string;
}) {
  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="card-title" style={{ padding: "4px 6px 8px" }}>
        {props.title || "조합 데이터셋"} <span className="muted small">{props.datasets.length}건</span>
      </div>
      <div className="col gap-4">
        {props.datasets.map((d) => (
          <button
            key={d.id}
            onClick={() => props.onSelect(d.id)}
            className={cx("card tight clickable", d.id === props.selectedId && "selected")}
            style={{ textAlign: "left", boxShadow: "none", cursor: "pointer", width: "100%" }}
          >
            <div className="bold ellipsis" title={d.title}>
              {d.title}
            </div>
            <div className="tiny muted ellipsis">
              {d.kind === "stream" ? "실시간 스트림" : d.asset.data_form || "파일"} · <span className="mono">{d.resource_id}</span>
            </div>
            {props.status && <div className="row wrap gap-4 mt-4">{props.status(d)}</div>}
          </button>
        ))}
      </div>
    </div>
  );
}

/** 준비도·확정 상태 배지 묶음 (STEP 3·4 목록에서 쓴다) */
export function ReadinessBadge({ d }: { d: Dataset }) {
  if (!d.readiness) return null;
  return d.readiness.level === "ai-ready" ? <Badge tone="ok">ai-ready</Badge> : <Badge tone="warn">초안 · 필수 {d.readiness.missing.length}건 결측</Badge>;
}

/** 프로파일된 표 1개의 컬럼 요약 */
export function ProfileTable({ table, asset, compact }: { table: TableProfile; asset?: Asset; compact?: boolean }) {
  const keyOf = (col: string) => asset?.key_candidates.find((k) => k.table === table.name && k.column === col);
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>컬럼</th>
            <th>타입</th>
            <th className="num">결측률</th>
            <th className="num">고유값</th>
            {!compact && <th>예시 값</th>}
            <th>감지</th>
          </tr>
        </thead>
        <tbody>
          {table.columns.map((c) => {
            const k = keyOf(c.name);
            return (
              <tr key={c.name}>
                <td className="bold">{c.name}</td>
                <td className="mono">{c.type}</td>
                <td className={cx("num", c.null_rate > 0.05 && "t-warn")}>{fmtPct(c.null_rate, 1)}</td>
                <td className="num">
                  {fmtNum(c.distinct)}
                  {c.unique ? " · 유일" : ""}
                </td>
                {!compact && (
                  <td className="muted ellipsis" style={{ maxWidth: 260 }} title={c.samples.join(", ")}>
                    {c.samples.slice(0, 3).join(", ")}
                  </td>
                )}
                <td>
                  <div className="row wrap gap-4">
                    {k && (
                      <span title={`${k.reason} · 점수 ${Math.round(k.score * 100)}`}>
                        <KeyPill code={k.code} label={k.label} />
                      </span>
                    )}
                    {c.pii && <Badge tone="err" title={`근거: ${c.pii.basis}`}>개인정보 의심 · {c.pii.kind}</Badge>}
                    {c.type === "datetime" && c.iso8601 === false && (
                      <Badge tone="warn" title={(c.date_formats || []).map((f) => `${f.format} ${f.count}건`).join(", ")}>
                        비표준 시각
                      </Badge>
                    )}
                    {c.interval?.label && <Badge tone="info">간격 {c.interval.label}</Badge>}
                    {c.missing_markers.filter((m) => m.marker !== "(빈 셀)").length > 0 && (
                      <Badge tone="warn" title={c.missing_markers.map((m) => `${m.marker} ${m.count}건`).join(", ")}>
                        결측 표기 {c.missing_markers.length}종
                      </Badge>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** 게이트 0 검사 5개 */
export function Gate0List({ checks }: { checks: Gate0Check[] }) {
  return (
    <div className="col gap-4">
      {checks.map((c) => (
        <div key={c.key} className="row top small">
          <span className={c.ok ? (c.skipped ? "muted" : "t-ok") : "t-err"} style={{ width: 16, flex: "none", fontWeight: 700 }}>
            {c.ok ? (c.skipped ? "–" : "✓") : "✕"}
          </span>
          <span className="bold nowrap">{c.name}</span>
          <span className="muted">{c.detail}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * 검증 결과 행 목록. 각 행의 [수정하러 이동] 은 위반의 원인 단계로 보낸다.
 * from 을 주면 이동한 화면 위에 '검증으로 복귀' 배너가 뜬다.
 */
export function ValidationRows(props: { rows: ValidationRow[]; datasetId: number; from?: number; hideInfo?: boolean; emptyText?: string }) {
  const { go, step } = useStudio();
  const rows = props.hideInfo ? props.rows.filter((r) => r.severity !== "Info") : props.rows;
  if (rows.length === 0) return <div className="small t-ok bold">{props.emptyText || "✓ 위반·경고 없음"}</div>;
  return (
    <div className="col gap-4">
      {rows.map((r, i) => (
        <div key={i} className="card tight flat row between top" style={{ padding: "8px 10px" }}>
          <div className="grow">
            <div className="row wrap gap-4">
              <SeverityBadge severity={r.severity} />
              <span className="bold small">{r.shape}</span>
              {r.path && <span className="kbd">{r.path}</span>}
            </div>
            <div className="small mt-4">{r.message}</div>
            {r.value && <div className="tiny muted mono ellipsis">값: {r.value}</div>}
          </div>
          {r.route && r.route.step !== step && (
            <Button size="sm" onClick={() => go(r.route!.step, { dataset: props.datasetId, focus: r.route!.focus, from: props.from, shape: r.shape })}>
              수정하러 이동 → STEP {r.route.step}
            </Button>
          )}
          {r.route && r.route.step === step && <span className="tiny muted nowrap">{r.route.label}</span>}
        </div>
      ))}
    </div>
  );
}

/** 편집할 수 없는 상태(종료·열람 전용)를 알리는 한 줄 */
export function ReadOnlyNote() {
  const { editable } = useStudio();
  if (editable) return null;
  return <div className="small muted">조회 전용 상태입니다 — 변경하려면 진행 중인 프로세스와 쓰기 권한이 필요합니다.</div>;
}
