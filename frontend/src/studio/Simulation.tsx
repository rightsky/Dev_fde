// STEP 7 오른쪽 패널 — AI 활용 시뮬레이션. 변환한 산출물을 실제 AI 서비스(챗봇 · 에이전트)가 쓰는 모습을 Claude 로 실행해 보인다.
// 핵심 화면은 Before/After 비교: 같은 질문에 '메타데이터 없이' 와 '산출물 포함' 이 어떻게 다르게 답하는지 한 눈에 보인다.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";
import type { SimulationRun, SimulationStatus } from "../types";
import { Badge, Banner, Button, QueryState, cx, fmtDateTime, fmtNum, useToast } from "../ui";

type Scenario = "chat" | "agent";

export function SimulationPanel({ pid }: { pid: number }) {
  const { canWrite } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["simulations", pid], queryFn: () => api.simulations(pid) });
  const [scenario, setScenario] = useState<Scenario>("chat");
  const [question, setQuestion] = useState("");
  const [picked, setPicked] = useState<number[] | null>(null); // null = 쓸 수 있는 전부
  const [compare, setCompare] = useState(true);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState<SimulationRun[] | null>(null);
  const [view, setView] = useState<"run" | "history">("run");

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
    <div className="card sim">
      <div className="sim-head">
        <h2>AI 활용 시뮬레이션</h2>
        <div className="row" style={{ gap: 10 }}>
          {st?.model && <span className="model">{st.model}</span>}
          <button className="link-btn" onClick={() => setView(view === "run" ? "history" : "run")}>
            {view === "run" ? `기록 ${fmtNum(st?.runs.length || 0)}` : "실행으로 돌아가기"}
          </button>
        </div>
      </div>
      <QueryState q={q}>
        {st && !st.enabled && <Banner tone="warn">AI 기능이 꺼져 있습니다. .env 에 FDE_ANTHROPIC_API_KEY 를 넣으면 켜집니다.</Banner>}
        {st && st.enabled && view === "history" && <History runs={st.runs} onPick={(g) => { setLatest(g); setView("run"); }} />}
        {st && st.enabled && view === "run" && (
          <>
            <div className="sim-seg" role="tablist">
              {st.scenarios.map((s) => (
                <button key={s.key} role="tab" aria-selected={s.key === scenario} className={cx(s.key === scenario && "on")} onClick={() => { setScenario(s.key); setLatest(null); }}>
                  {s.label}
                  <small>{s.key === "chat" ? "산출물을 읽고 질문에 답합니다" : "도구를 골라 카탈로그를 탐색합니다"}</small>
                </button>
              ))}
            </div>

            {scenario === "chat" ? (
              <div>
                <div className="sim-label">문맥으로 줄 데이터셋</div>
                <div className="sim-targets">
                  {st.datasets.map((d) => {
                    const off = !!d.blocked_reason || !d.has_artifacts;
                    const on = !off && selected.includes(d.id);
                    return (
                      <label key={d.id} className={cx(off && "off", on && "on")} title={d.blocked_reason || (!d.has_artifacts ? "변환 산출물이 없습니다. 먼저 변환을 실행하세요" : undefined)}>
                        <input type="checkbox" disabled={off} checked={on} onChange={() => setPicked(on ? selected.filter((x) => x !== d.id) : [...selected, d.id])} />
                        <span className="grow">{d.title}</span>
                        {d.blocked_reason && <Badge tone="err">외부 전송 제외</Badge>}
                        {!d.has_artifacts && !d.blocked_reason && <Badge tone="warn">산출물 없음</Badge>}
                      </label>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="small dim">
                발행된 카탈로그 {fmtNum(st.published_count)}건이 대상입니다.
                {st.published_count === 0 && <span className="t-warn"> 발행된 항목이 없어 검색 결과가 비어 있을 것입니다.</span>}
                {st.datasets.some((d) => d.blocked_reason) && <span> 외부 전송 제외 데이터셋은 검색에서 빠집니다.</span>}
              </div>
            )}

            <div>
              <div className="sim-label">질문</div>
              <div className="sim-examples" style={{ marginBottom: 6 }}>
                {sc?.examples.map((ex) => (
                  <button key={ex} onClick={() => setQuestion(ex)}>{ex}</button>
                ))}
              </div>
              <textarea className="textarea" rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="예시를 고르거나 직접 적으세요" />
            </div>

            <div className="sim-run">
              <label className="check small" title="같은 질문을 메타데이터 없이 한 번 더 실행해 나란히 봅니다">
                <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
                메타데이터 없이 한 번 더 실행해 비교
              </label>
              <Button variant="primary" busy={busy} disabled={!canWrite || !question.trim() || (scenario === "chat" && selected.length === 0)} onClick={run}>
                {compare ? "비교 실행" : "실행"}
              </Button>
            </div>
            {busy && (
              <div className="sim-wait">
                <span className="spinner" /> Claude 가 답하는 중입니다. 에이전트는 도구를 여러 번 부르느라 30초 넘게 걸릴 수 있습니다.
              </div>
            )}

            {latest ? <Results runs={latest} /> : !busy && (
              <div className="sim-empty">
                질문을 고르고 실행하면 결과가 여기 나옵니다.
                <br />
                비교를 켜면 왼쪽에 메타데이터(또는 도구) 없이 답한 것, 오른쪽에 이 스튜디오의 결과물을 준 것이 나란히 보입니다.
              </div>
            )}
          </>
        )}
      </QueryState>
    </div>
  );
}

// ───────────── 결과

function Results({ runs }: { runs: SimulationRun[] }) {
  const sorted = [...runs].sort((a, b) => Number(a.with_metadata) - Number(b.with_metadata));
  const pair = sorted.length === 2 && !!sorted[0].group_id && sorted[0].group_id === sorted[1].group_id;
  const [before, after] = pair ? sorted : [null, sorted[sorted.length - 1]];
  return (
    <div className="col gap-10">
      <hr className="divider" style={{ margin: 0 }} />
      <div className="sim-q">{after.question}</div>
      {pair && before && <Scoreboard before={before} after={after} />}
      {pair && before ? (
        <div className="sim-pair">
          <Answer r={before} />
          <Answer r={after} />
        </div>
      ) : (
        <Answer r={after} />
      )}
      <div className="sim-foot">
        {pair ? "두 답 모두 같은 모델입니다. 차이는 모델에 준 정보뿐입니다." : after.scenario === "agent" ? "카탈로그 도구를 쓴 결과입니다." : "산출물을 문맥으로 준 결과입니다."} 실행 {fmtDateTime(after.created_at)}
      </div>
    </div>
  );
}

const SIDE = {
  chat: { before: "메타데이터 없이", after: "산출물 포함" },
  agent: { before: "도구 없이", after: "카탈로그 도구 사용" },
};

function Scoreboard({ before, after }: { before: SimulationRun; after: SimulationRun }) {
  const agent = after.scenario === "agent";
  const side = SIDE[after.scenario];
  const cell = (r: SimulationRun, k: "answered" | "sources" | "tools" | "tokens" | "time") => {
    const res = r.result;
    if (k === "answered") return res.answered === undefined ? (res.answer ? "답함" : "응답 없음") : res.answered ? "답함" : "답하지 못함";
    if (k === "sources") return `${res.sources?.length ?? 0}건`;
    if (k === "tools") return `${res.tool_calls ?? 0}회`;
    if (k === "tokens") return fmtNum(r.usage.input_tokens + r.usage.output_tokens);
    return `${(r.duration_ms / 1000).toFixed(1)}s`;
  };
  const rows: [string, "answered" | "sources" | "tools" | "tokens" | "time"][] = agent
    ? [["도구 호출", "tools"], ["토큰", "tokens"], ["소요", "time"]]
    : [["답변", "answered"], ["근거 속성", "sources"], ["토큰", "tokens"], ["소요", "time"]];
  return (
    <div className="sim-score">
      <div />
      <div className="hd">{side.before}</div>
      <div className="hd">{side.after}</div>
      {rows.map(([label, k]) => (
        <RowFrag key={k} label={label} a={cell(before, k)} b={cell(after, k)} />
      ))}
    </div>
  );
}

function RowFrag({ label, a, b }: { label: string; a: string; b: string }) {
  return (
    <>
      <div>{label}</div>
      <div>{a}</div>
      <div className="bold">{b}</div>
    </>
  );
}

function Answer({ r }: { r: SimulationRun }) {
  const res = r.result;
  const after = r.with_metadata;
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className={cx("sim-who", after && "after")}>
        <span className="dot" />
        {after ? SIDE[r.scenario].after : SIDE[r.scenario].before}
        {r.scenario === "agent" && after && res.tools_available && <span className="muted">· 도구 {res.tools_available.length}개</span>}
      </div>
      <div className={cx("sim-a", after ? "after" : "before")}>{res.answer || "(응답 없음)"}</div>
      {res.sources && res.sources.length > 0 && (
        <div className="sim-ev">
          {res.sources.map((s, i) => (
            <div key={i}>
              <code title={s.dataset}>{s.property}</code>
              <span className="v">{s.value}</span>
            </div>
          ))}
        </div>
      )}
      {res.missing && res.missing.length > 0 && (
        <div className="sim-miss">
          <span className="t">있으면 답할 수 있는 항목</span>
          {res.missing.map((m) => <span key={m}>{m}</span>)}
        </div>
      )}
      {res.trace && res.trace.length > 0 && (
        <>
          <button className="link-btn small" style={{ marginTop: 8 }} onClick={() => setOpen((v) => !v)}>
            {open ? "도구 호출 접기" : `도구 호출 ${res.trace.length}회 펼치기`}
          </button>
          {open && (
            <div className="sim-trace">
              {res.trace.map((t, i) => (
                <div key={i} className={t.status}>
                  <code>{t.tool}</code> <span className="args">{Object.entries(t.arguments).map(([k, v]) => `${k}=${String(v)}`).join(" ")}</span>
                  {t.status !== "ok" && <Badge tone={t.status === "denied" ? "warn" : "err"}>{t.status === "denied" ? "거부" : "오류"}</Badge>}
                  {t.resource_ids.length > 0 && <span className="args"> → {t.resource_ids.slice(0, 4).join(", ")}</span>}
                  <div className="pv">{t.preview}</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ───────────── 기록

function History({ runs, onPick }: { runs: SimulationRun[]; onPick: (g: SimulationRun[]) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  if (runs.length === 0) return <div className="sim-empty">아직 실행한 기록이 없습니다.</div>;
  const groups: SimulationRun[][] = [];
  const seen = new Set<string>();
  for (const r of runs) {
    if (r.group_id) {
      if (seen.has(r.group_id)) continue;
      seen.add(r.group_id);
      groups.push(runs.filter((x) => x.group_id === r.group_id));
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
    <div className="sim-hist">
      {groups.map((g) => (
        <div key={g[0].id} onClick={() => onPick(g)}>
          <div className="row between wrap small">
            <span>
              <Badge tone={g[0].scenario === "agent" ? "purple" : "info"}>{g[0].scenario_label}</Badge> {g.length === 2 && <Badge>비교</Badge>}
            </span>
            <span className="muted">
              {fmtDateTime(g[0].created_at)} {g[0].created_by}{" "}
              <button className="link-btn danger" onClick={(e) => { e.stopPropagation(); void remove(g); }}>삭제</button>
            </span>
          </div>
          <div className="q">{g[0].question}</div>
        </div>
      ))}
    </div>
  );
}

export type { SimulationStatus };
