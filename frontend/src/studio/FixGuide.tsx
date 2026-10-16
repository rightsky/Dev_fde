// STEP 8 에서 '수정하러 이동' 으로 넘어왔을 때 대상 단계 위에 붙는 수정 작업 안내.
// 어디를(위치) 어떻게(판정 기준 · 조치 방법) 고쳐야 하는지와, 지금 이 데이터셋의 판정 사유를 보여 주고, 끝나면 STEP 8 로 돌아가 재진단하게 한다.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useReference } from "../auth";
import type { DiagItem, DiagStatus } from "../types";
import { Badge, Button, cx } from "../ui";
import type { GoOptions } from "./context";

const STATUS: Record<DiagStatus, { label: string; tone: "ok" | "warn" | "err" | "muted" | "info" }> = {
  met: { label: "충족", tone: "ok" },
  partial: { label: "부분 충족", tone: "warn" },
  unmet: { label: "미흡", tone: "err" },
  na: { label: "해당 없음", tone: "muted" },
  pending: { label: "확인 대기", tone: "info" },
};
// focus 이름 → 화면 위치 설명 (필드가 아닌 영역)
const PLACE: Record<string, string> = {
  classes: "① 클래스 탭",
  dictionary: "③ 데이터 사전 탭",
  combo: "조합 구성",
  mint: "발행 ID 민팅",
  N2SF: "보안등급(N²SF) 축",
  K: "연계키(K) 축",
};

export function FixGuide(props: { pid: number; itemId: string; datasetId: number | null; step: number; go: (n: number, o?: GoOptions) => void }) {
  const { pid, itemId, datasetId, step, go } = props;
  const ref = useReference();
  const q = useQuery({ queryKey: ["process", pid, "diagnosis", "latest"], queryFn: () => api.latestDiagnosis(pid), staleTime: 30_000 });
  const [collapsed, setCollapsed] = useState(false);
  const items: DiagItem[] = q.data?.run?.items ?? [];
  const item = items.find((i) => i.id === itemId);
  // 이 항목과 같은 단계로 가는 다른 미흡·부분·확인 대기 항목 (순서대로 처리할 수 있게)
  const queue = useMemo(
    () => items.filter((i) => i.route && (i.status === "unmet" || i.status === "partial" || i.status === "pending")),
    [items],
  );
  if (!item) return null;

  const row = item.datasets.find((d) => d.id === datasetId) ?? item.datasets.find((d) => d.status !== "met" && d.status !== "na");
  const focus = row?.focus ?? item.route?.focus ?? null;
  const field = focus ? ref.meta_fields.find((f) => f.name === focus || (focus === "publisher" && f.name === "publisher_org_id")) : undefined;
  const place = focus ? (field ? `프러퍼티 폼${field.group === "card" || field.group === "ai" ? " › ④ 데이터 카드 탭" : ""} › "${field.label.split(" (")[0]}"` : PLACE[focus] ?? focus) : item.route?.label ?? `STEP ${step}`;
  const st = STATUS[item.status];
  const idx = queue.findIndex((i) => i.id === item.id);
  const next = idx >= 0 ? queue[(idx + 1) % queue.length] : null;
  const openRows = item.datasets.filter((d) => d.status !== "met" && d.status !== "na");

  return (
    <div className={cx("fixguide", collapsed && "collapsed")} role="region" aria-label="수정 작업 안내">
      <div className="fixguide-bar">
        <div className="fixguide-title">
          <span className="fixguide-id">{item.id}</span>
          <b>{item.name}</b>
          <Badge tone={st.tone}>{st.label}</Badge>
          {item.level && item.level !== "원칙" && <Badge>{item.level}</Badge>}
          {row && <span className="muted small">· {row.name}</span>}
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button className="link-btn small" onClick={() => setCollapsed((v) => !v)}>
            {collapsed ? "안내 펼치기" : "접기"}
          </button>
          {next && next.id !== item.id && (
            <Button size="sm" title={`${next.id} ${next.name} (STEP ${next.route!.step})`}
              onClick={() => go(next.route!.step, { fix: next.id, focus: next.datasets.find((d) => d.status !== "met")?.focus ?? next.route!.focus,
                                                    dataset: next.datasets.find((d) => d.status !== "met")?.id })}>
              다음 항목 {next.id}
            </Button>
          )}
          <Button size="sm" variant="dark" onClick={() => go(8, { focus: item.id })}>
            STEP 8 로 돌아가 재진단
          </Button>
        </div>
      </div>
      {!collapsed && (
        <div className="fixguide-body">
          <div className="fixguide-cell">
            <div className="fixguide-k">위치</div>
            <div className="fixguide-v">
              <b>STEP {step}</b> › {place}
              {focus && field && <div className="muted small">주황 테두리로 표시한 칸입니다 · 속성 <span className="mono">{field.property}</span></div>}
            </div>
          </div>
          <div className="fixguide-cell">
            <div className="fixguide-k">지금 판정</div>
            <div className="fixguide-v">
              {row ? row.detail : item.evidence[0] ?? "사유 없음"}
              {openRows.length > 1 && (
                <div className="small muted">
                  이 항목에서 고칠 데이터셋 {openRows.length}건:{" "}
                  {openRows.map((d) => (
                    <button key={d.id} className={cx("link-btn small", d.id === row?.id && "bold")} onClick={() => go(step, { fix: item.id, dataset: d.id, focus: d.focus ?? focus })}>
                      {d.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="fixguide-cell">
            <div className="fixguide-k">충족 기준</div>
            <div className="fixguide-v">{item.criteria || item.text || "—"}</div>
          </div>
          <div className="fixguide-cell">
            <div className="fixguide-k">할 일</div>
            <div className="fixguide-v">
              {item.remedy || "값을 채우고 저장한 뒤 STEP 8 에서 재진단합니다"}
              <div className="small muted">저장하면 검증·변환 결과가 "최신 아님"이 되므로 STEP 6 재검증 → STEP 7 재변환 → STEP 8 재진단 순으로 다시 실행합니다.</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
