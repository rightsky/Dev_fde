// 발행 검수 공용 부품 — 위험 수준 배지, 위험 신호 목록, 발행 대상 표 (STEP 7 발행 카드와 검수 큐가 같이 쓴다)
import { Link } from "react-router-dom";
import type { ReviewDataset, ReviewSignal, RiskLevel } from "../types";
import { Badge } from "../ui";

const LEVEL: Record<RiskLevel, { label: string; tone: "err" | "warn" | "ok" }> = {
  high: { label: "위험 높음", tone: "err" },
  medium: { label: "위험 보통", tone: "warn" },
  low: { label: "위험 낮음", tone: "ok" },
};
const SEV: Record<RiskLevel, { label: string; tone: "err" | "warn" | "info" }> = {
  high: { label: "높음", tone: "err" },
  medium: { label: "보통", tone: "warn" },
  low: { label: "참고", tone: "info" },
};
const TERM_SHORT: [string, string][] = [
  ["ai_training", "학습"],
  ["ai_combination", "결합"],
  ["ai_automated_access", "자동화"],
  ["ai_bulk_access", "대량"],
  ["ai_redistribution", "재배포"],
];
const TERM_STATUS: Record<string, { label: string; tone: "ok" | "warn" | "err" }> = {
  permitted: { label: "허용", tone: "ok" },
  conditional: { label: "조건부", tone: "warn" },
  prohibited: { label: "불허", tone: "err" },
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return <Badge tone={LEVEL[level].tone}>{LEVEL[level].label}</Badge>;
}

export const STATUS_TONE: Record<string, "info" | "ok" | "err" | "muted"> = { pending: "info", approved: "ok", rejected: "err", withdrawn: "muted" };

/** 위험 신호. checked/onToggle 을 주면 고위험 신호 옆에 확인란을 그린다 (승인자 확인용). */
export function SignalList(props: { signals: ReviewSignal[]; checked?: Set<string>; onToggle?: (code: string) => void; acknowledged?: string[] }) {
  if (props.signals.length === 0) return <div className="small muted">위험 신호가 없습니다</div>;
  const order: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };
  const rows = [...props.signals].sort((a, b) => order[a.severity] - order[b.severity]);
  return (
    <div className="col gap-8">
      {rows.map((s) => {
        const ackable = s.severity === "high" && props.onToggle;
        const acked = props.acknowledged?.includes(s.code);
        return (
          <div key={s.code} className="card tight flat" style={s.severity === "high" ? { borderColor: "var(--err-line)" } : undefined}>
            <div className="row between top wrap">
              <div className="row top" style={{ gap: 8 }}>
                {ackable && (
                  <input
                    type="checkbox"
                    aria-label={`${s.label} 확인`}
                    checked={props.checked?.has(s.code) ?? false}
                    onChange={() => props.onToggle?.(s.code)}
                    style={{ marginTop: 3 }}
                  />
                )}
                <div>
                  <span className="bold">{s.label}</span>
                  <div className="small dim">{s.detail}</div>
                  {s.datasets.length > 0 && <div className="small mono muted mt-4">{s.datasets.join(" · ")}</div>}
                </div>
              </div>
              <div className="row">
                {acked && <Badge tone="ok">승인자 확인</Badge>}
                <Badge tone={SEV[s.severity].tone}>{SEV[s.severity].label}</Badge>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function DatasetTable({ rows, published }: { rows: ReviewDataset[]; published?: string[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>발행 ID</th>
            <th>제목</th>
            <th>발행</th>
            <th>N²SF</th>
            <th>개인정보 의심</th>
            <th>AI 이용조건</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.resource_id}>
              <td className="mono nowrap">
                {published?.includes(d.resource_id) ? <Link to={`/catalog/${encodeURIComponent(d.resource_id)}`}>{d.resource_id}</Link> : d.resource_id}
              </td>
              <td className="bold">{d.title}</td>
              <td className="nowrap">
                {d.change === "new" ? <Badge tone="info">신규</Badge> : d.change === "update" ? <Badge tone="warn">v{d.current_version} → v{(d.current_version ?? 0) + 1}</Badge> : <Badge>변경 없음</Badge>}
              </td>
              <td>{d.n2sf ? <Badge tone={d.n2sf === "O" ? "ok" : "err"}>{d.n2sf}</Badge> : <Badge tone="warn">미지정</Badge>}</td>
              <td className="small">{d.pii.length ? <span className="t-err">{d.pii.join(", ")}</span> : <span className="muted">없음</span>}</td>
              <td>
                <div className="row wrap" style={{ gap: 3 }}>
                  {TERM_SHORT.map(([k, label]) => {
                    const st = TERM_STATUS[d.ai_terms?.[k]];
                    return (
                      <Badge key={k} tone={st?.tone || "muted"}>
                        {label} {st?.label || "미정"}
                      </Badge>
                    );
                  })}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
