// STEP 7 오른쪽 패널 — AI 활용 시뮬레이션. 변환한 산출물을 실제 AI 서비스(챗봇 · 에이전트)가 쓰는 모습을 Claude 로 실행해 보인다.
// Before/After: 같은 질문을 메타데이터 없이 / 포함해서 두 번 실행해 나란히 본다.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";
import type { SimulationRun, SimulationStatus } from "../types";
import { Badge, Banner, Button, Empty, QueryState, Tabs, fmtDateTime, fmtNum, useToast } from "../ui";

type Scenario = "chat" | "agent";

export function SimulationPanel({ pid }: { pid: number }) {
  const { canWrite } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["simulations", pid], queryFn: () => api.simulations(pid) });
  const [scenario, setScenario] = useState<Scenario>("chat");
  const [question, setQuestion] = useState("");
  const [picked, setPicked] = useState<number[] | null>(null); // null = 전체(차단 제외)
  const [compare, setCompare] = useState(true);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState<SimulationRun[] | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const st = q.data;
  const usable = (st?.datasets || []).filter((d) => !d.blocked_reason && d.has_artifacts);
  const selected = picked ?? usable.map((d) => d.id);
  const sc = st?.scenarios.find((s) => s.key === scenario);

  const run = async () => {
    if (!question.trim()) return;
    setBusy(true);
    try {
      const r = await api.runSimulation(pid, { scenario, question, dataset_ids: scenario === "chat" ? selected : [], compare });
      setLatest(r.runs);
      await qc.invalidateQueries({ queryKey: ["simulations", pid] });
      await qc.invalidateQueries({ queryKey: ["process", pid, "activities"] });
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ position: "sticky", top: 0 }}>
      <div className="card-head">
        <div className="card-title">
          ✦ AI 활용 시뮬레이션 {st?.model && <Badge tone="purple">{st.model}</Badge>}
        </div>
        <button className="link-btn" onClick={() => setShowHistory((v) => !v)}>
          {showHistory ? "실행으로" : `기록 ${fmtNum(st?.runs.length || 0)}`}
        </button>
      </div>
      <QueryState q={q}>
        {st && !st.enabled && <Banner tone="warn">AI 기능이 꺼져 있습니다 — .env 에 FDE_ANTHROPIC_API_KEY 를 지정하면 켜집니다.</Banner>}
        {st && st.enabled && showHistory && <History runs={st.runs} onPick={(g) => { setLatest(g); setShowHistory(false); }} />}
        {st && st.enabled && !showHistory && (
          <div className="col gap-12">
            <p className="small muted" style={{ margin: 0 }}>
              이 프로세스의 산출물(JSON-LD · 데이터 카드 · 데이터 사전)이나 발행된 카탈로그를 실제 AI 서비스가 어떻게 쓰는지 보입니다. 원본 데이터 파일은 보내지 않습니다. 실행은 활동 로그에 남습니다.
            </p>
            <Tabs tabs={st.scenarios.map((s) => ({ key: s.key, label: s.label }))} value={scenario} onChange={(k) => { setScenario(k); setLatest(null); }} />
            {sc && <div className="small dim">{sc.desc}</div>}

            {scenario === "chat" ? (
              <div className="col gap-4">
                <span className="small bold dim">대상 데이터셋</span>
                {st.datasets.map((d) => {
                  const off = !!d.blocked_reason || !d.has_artifacts;
                  return (
                    <label key={d.id} className="check small" title={d.blocked_reason || (!d.has_artifacts ? "변환 산출물이 없습니다 — 먼저 변환을 실행하세요" : undefined)}>
                      <input
                        type="checkbox"
                        disabled={off}
                        checked={!off && selected.includes(d.id)}
                        onChange={() => setPicked(selected.includes(d.id) ? selected.filter((x) => x !== d.id) : [...selected, d.id])}
                      />
                      {d.title}
                      {d.blocked_reason && <Badge tone="err">외부 전송 제외</Badge>}
                      {!d.has_artifacts && !d.blocked_reason && <Badge tone="warn">산출물 없음</Badge>}
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="small dim">
                발행된 카탈로그 {fmtNum(st.published_count)}건을 대상으로 모델이 도구를 골라 호출합니다.
                {st.published_count === 0 && <span className="t-warn"> 발행된 항목이 없어 검색 결과가 비어 있을 것입니다.</span>}
                {st.datasets.some((d) => d.blocked_reason) && <span> 외부 전송 제외 데이터셋은 검색에서 빠집니다.</span>}
              </div>
            )}

            <div className="col gap-4">
              <span className="small bold dim">질문 · 요청</span>
              <div className="row wrap" style={{ gap: 4 }}>
                {sc?.examples.map((ex) => (
                  <button key={ex} className="chip" onClick={() => setQuestion(ex)} title="예시 질문 넣기">
                    {ex.length > 26 ? ex.slice(0, 26) + "…" : ex}
                  </button>
                ))}
              </div>
              <textarea className="textarea" rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={sc?.examples[0]} />
            </div>
            <div className="row between wrap">
              <label className="check small" title="같은 질문을 메타데이터 없이(파일명·컬럼명만 / 도구 없음) 한 번 더 실행해 나란히 봅니다">
                <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
                Before/After 비교 (메타데이터 없이 vs 포함)
              </label>
              <Button variant="primary" busy={busy} disabled={!canWrite || !question.trim() || (scenario === "chat" && selected.length === 0)} onClick={run}>
                실행{compare ? " (2회 호출)" : ""}
              </Button>
            </div>
            {busy && <div className="small muted">모델을 호출하는 중입니다 — 에이전트는 도구를 여러 번 부르느라 30초 넘게 걸릴 수 있습니다.</div>}

            {latest && <Results runs={latest} />}
          </div>
        )}
      </QueryState>
    </div>
  );
}

function Results({ runs }: { runs: SimulationRun[] }) {
  const pair = runs.length === 2 && runs[0].group_id && runs[0].group_id === runs[1].group_id;
  return (
    <div className="col gap-8">
      <hr className="divider" />
      {pair ? (
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {runs.map((r) => <RunCard key={r.id} r={r} />)}
        </div>
      ) : (
        runs.map((r) => <RunCard key={r.id} r={r} />)
      )}
      {pair && (
        <div className="small dim">
          왼쪽은 메타데이터를 적지 않았을 때 AI 가 아는 전부(파일명·컬럼명 / 도구 없음)로 답한 것, 오른쪽은 이 스튜디오의 산출물을 준 것입니다.
        </div>
      )}
    </div>
  );
}

function RunCard({ r }: { r: SimulationRun }) {
  const res = r.result;
  const [open, setOpen] = useState(false);
  return (
    <div className="card tight flat" style={{ borderColor: r.with_metadata ? "var(--ok-line)" : "var(--line-strong)" }}>
      <div className="row between wrap">
        <Badge tone={r.with_metadata ? "ok" : "muted"}>{r.with_metadata ? "After · 메타데이터 포함" : "Before · 메타데이터 없음"}</Badge>
        <span className="small muted">
          {(r.duration_ms / 1000).toFixed(1)}s · 토큰 {fmtNum(r.usage.input_tokens + r.usage.output_tokens)}
          {r.scenario === "agent" && ` · 도구 ${res.tool_calls ?? 0}회`}
        </span>
      </div>
      {res.answered === false && <div className="small t-warn mt-4">답하지 못함</div>}
      <div className="mt-8" style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{res.answer || <span className="muted">(응답 없음)</span>}</div>
      {res.missing && res.missing.length > 0 && (
        <div className="small mt-8">
          <span className="bold dim">답하려면 필요한 항목:</span> {res.missing.join(", ")}
        </div>
      )}
      {res.sources && res.sources.length > 0 && (
        <div className="mt-8">
          <div className="small bold dim">근거로 쓴 메타데이터 {res.sources.length}건</div>
          <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 16 }}>
            {res.sources.map((s, i) => (
              <li key={i}>
                <span className="mono">{s.property}</span>
                {s.dataset && <span className="muted"> · {s.dataset}</span>}: {s.value}
              </li>
            ))}
          </ul>
        </div>
      )}
      {res.trace && res.trace.length > 0 && (
        <div className="mt-8">
          <button className="link-btn small" onClick={() => setOpen((v) => !v)}>
            {open ? "도구 호출 접기" : `도구 호출 ${res.trace.length}회 보기`}
          </button>
          {open && (
            <ol className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
              {res.trace.map((t, i) => (
                <li key={i} className="mb-4">
                  <span className="mono">{t.tool}</span>
                  <span className="muted"> {Object.entries(t.arguments).map(([k, v]) => `${k}=${String(v)}`).join(" ")}</span>{" "}
                  <Badge tone={t.status === "ok" ? "ok" : t.status === "denied" ? "warn" : "err"}>{t.status}</Badge>
                  {t.resource_ids.length > 0 && <span className="mono muted"> → {t.resource_ids.slice(0, 4).join(", ")}</span>}
                  <div className="muted" style={{ wordBreak: "break-all" }}>{t.preview.slice(0, 160)}{t.preview.length > 160 ? "…" : ""}</div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
      {r.with_metadata && res.context_parts && (
        <div className="small muted mt-8">
          문맥: {Object.entries(res.context_parts).map(([k, v]) => `${k}(${v.map((x) => x.replace("dcat_jsonld", "JSON-LD").replace("data_card_markdown", "카드").replace("data_dictionary_csv", "사전")).join("·")})`).join(", ")}
        </div>
      )}
    </div>
  );
}

function History({ runs, onPick }: { runs: SimulationRun[]; onPick: (g: SimulationRun[]) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  if (runs.length === 0) return <Empty>실행 기록이 없습니다</Empty>;
  // Before/After 묶음은 한 줄로
  const groups: SimulationRun[][] = [];
  const seen = new Set<string>();
  for (const r of runs) {
    if (r.group_id) {
      if (seen.has(r.group_id)) continue;
      seen.add(r.group_id);
      groups.push(runs.filter((x) => x.group_id === r.group_id).sort((a, b) => Number(a.with_metadata) - Number(b.with_metadata)));
    } else groups.push([r]);
  }
  const remove = async (g: SimulationRun[]) => {
    try {
      await Promise.all(g.map((r) => api.deleteSimulation(r.id)));
      await qc.invalidateQueries({ queryKey: ["simulations", g[0].process_id] });
    } catch (e) {
      toast.error(e);
    }
  };
  return (
    <div className="col gap-4">
      {groups.map((g) => (
        <div key={g[0].id} className="card tight flat clickable" onClick={() => onPick(g)}>
          <div className="row between wrap">
            <span className="small">
              <Badge tone={g[0].scenario === "agent" ? "purple" : "info"}>{g[0].scenario_label}</Badge> {g.length === 2 && <Badge>Before/After</Badge>}
            </span>
            <span className="small muted">
              {fmtDateTime(g[0].created_at)} · {g[0].created_by}{" "}
              <button className="link-btn danger" onClick={(e) => { e.stopPropagation(); void remove(g); }}>
                삭제
              </button>
            </span>
          </div>
          <div className="small mt-4">{g[0].question}</div>
        </div>
      ))}
    </div>
  );
}

export type { SimulationStatus };
