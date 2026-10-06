import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Outlet, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, useReference } from "../auth";
import type { Process, ProcessDetail } from "../types";
import { Badge, Banner, Button, ConfirmButton, Empty, Loading, Modal, QueryState, cx, errText, fmtDateTime, useToast } from "../ui";
import { StudioCtx } from "./context";
import type { GoOptions, StudioValue } from "./context";

/** /studio — 가장 최근에 작업한 진행 중 프로세스로 보낸다. 없으면 시작 화면. */
export function StudioIndex() {
  const { canWrite } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const q = useQuery({ queryKey: ["processes", "all"], queryFn: () => api.processes() });
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      const d = await api.createProcess();
      nav(`/studio/${d.process.id}/step/1`, { replace: true });
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  if (q.isLoading) return <div className="main no-bar"><Loading /></div>;
  if (q.error) return <div className="main no-bar"><Banner tone="err">{errText(q.error)}</Banner></div>;
  const active = (q.data || []).find((p) => p.status === "active");
  if (active) return <Navigate to={`/studio/${active.id}/step/${active.current_step}`} replace />;
  return (
    <div className="main no-bar">
      <h1 className="page-title">ARD 스튜디오</h1>
      <p className="page-sub">8단계 워크플로로 원천 데이터에 DCAT · PROV-O 메타데이터를 입히고, SHACL 로 검증한 뒤 카탈로그에 발행합니다.</p>
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-title">진행 중인 프로세스가 없습니다</div>
        <p className="muted mt-4">프로세스는 8단계 작업 1회분입니다. 조합·메타데이터·검증 결과가 프로세스 단위로 서버에 저장됩니다.</p>
        <div className="row mt-12">
          <Button variant="primary" busy={busy} disabled={!canWrite} onClick={create}>
            ＋ 새 프로세스 시작
          </Button>
          {!canWrite && <span className="small muted">열람 전용 계정입니다</span>}
        </div>
        {(q.data || []).length > 0 && (
          <>
            <hr className="divider" />
            <div className="small bold dim mb-8">종료된 프로세스</div>
            <div className="col">
              {(q.data || []).map((p) => (
                <button key={p.id} className="link-btn" style={{ textAlign: "left" }} onClick={() => nav(`/studio/${p.id}/step/${p.current_step}`)}>
                  {p.name} <span className="muted small">· {fmtDateTime(p.updated_at)}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function StudioLayout() {
  const params = useParams();
  const pid = Number(params.pid);
  const step = Math.max(1, Math.min(8, Number(params.step) || 1));
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const { canWrite, isAdmin } = useAuth();
  const reference = useReference();
  const [listOpen, setListOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);

  const q = useQuery({ queryKey: ["process", pid], queryFn: () => api.process(pid), enabled: Number.isFinite(pid) });
  const detail = q.data;

  const refresh = useCallback(async () => {
    await qc.invalidateQueries({ queryKey: ["process", pid] });
  }, [qc, pid]);

  const guard = useRef<(() => boolean) | null>(null);

  const go = useCallback(
    (n: number, opts?: GoOptions) => {
      // 변경 직후(refresh 뒤) 곧바로 호출해도 맞게 판정하도록, 닫힌 값이 아니라 조회 캐시의 최신 상태를 본다
      const detail = qc.getQueryData<ProcessDetail>(["process", pid]);
      if (!detail) return;
      const g = detail.state.gates.find((x) => x.step === n);
      if (g && !g.can_enter) {
        toast(`🔒 STEP ${n} 잠김 — ${g.reason}`);
        return;
      }
      if (guard.current?.() && !window.confirm("저장하지 않은 변경이 있습니다. 저장하지 않고 이동할까요?")) return;
      const qs = new URLSearchParams();
      if (opts?.dataset) qs.set("ds", String(opts.dataset));
      if (opts?.focus) qs.set("focus", opts.focus);
      if (opts?.from) qs.set("from", String(opts.from));
      if (opts?.shape) qs.set("shape", opts.shape);
      const s = qs.toString();
      nav(`/studio/${pid}/step/${n}${s ? `?${s}` : ""}`);
      if (canWrite && detail.process.status === "active" && detail.process.current_step !== n) {
        api.updateProcess(pid, { current_step: n }).then((d) => qc.setQueryData(["process", pid], d)).catch(() => undefined);
      }
    },
    [nav, pid, toast, canWrite, qc],
  );

  // 잠긴 단계의 주소로 직접 들어오면 들어갈 수 있는 마지막 단계로 되돌린다
  useEffect(() => {
    if (!detail) return;
    const g = detail.state.gates.find((x) => x.step === step);
    if (g && !g.can_enter) {
      let n = step;
      while (n > 1 && !detail.state.gates.find((x) => x.step === n)?.can_enter) n--;
      toast(`🔒 STEP ${step} 잠김 — ${g.reason}`);
      nav(`/studio/${pid}/step/${n}`, { replace: true });
    }
  }, [detail, step, pid, nav, toast]);

  const value: StudioValue | null = useMemo(() => {
    if (!detail) return null;
    const num = (k: string) => (sp.get(k) ? Number(sp.get(k)) : null);
    return {
      pid,
      step,
      detail,
      combo: detail.datasets.filter((d) => d.in_combo).sort((a, b) => a.position - b.position),
      reference,
      editable: canWrite && detail.process.status === "active",
      isAdmin,
      gate: (n: number) => detail.state.gates.find((g) => g.step === n)!,
      go,
      refresh,
      guard,
      params: { dataset: num("ds"), focus: sp.get("focus"), from: num("from"), shape: sp.get("shape") },
    };
  }, [detail, pid, step, reference, canWrite, isAdmin, go, refresh, sp]);

  if (!Number.isFinite(pid)) return <Navigate to="/studio" replace />;
  if (q.isLoading) return <div className="main no-bar"><Loading label="프로세스를 불러오는 중" /></div>;
  if (q.error || !detail || !value) {
    return (
      <div className="main no-bar">
        <Banner tone="err" right={<Button size="sm" onClick={() => nav("/studio")}>스튜디오 처음으로</Button>}>
          {errText(q.error) || "프로세스를 찾을 수 없습니다"}
        </Banner>
      </div>
    );
  }
  const p = detail.process;
  const st = detail.state;
  const staleOf: Record<number, string | null> = { 6: st.validation.stale, 7: st.serialization.stale, 8: st.diagnosis.stale };

  return (
    <StudioCtx.Provider value={value}>
      <div className="body">
        <aside className="sidebar">
          <div className="sidebar-title">워크플로 8단계</div>
          {reference.steps.map((s) => {
            const g = value.gate(s.n);
            const stale = !!staleOf[s.n] && !g.done;
            return (
              <button
                key={s.n}
                className={cx("step-row", s.n === step && "current", g.done && "done", stale && "stale", !g.can_enter && "locked")}
                onClick={() => go(s.n)}
                title={!g.can_enter ? g.reason : stale ? staleOf[s.n] || "" : ""}
              >
                <span className="step-dot">{!g.can_enter ? "🔒" : g.done ? "✓" : stale ? "!" : s.n}</span>
                <span>
                  <div className="step-n">STEP {s.n}</div>
                  <div className="step-label">{s.label}</div>
                  {(stale || g.progress) && <div className="step-progress">{stale ? "재실행 필요" : g.progress}</div>}
                </span>
              </button>
            );
          })}
          <div className="sidebar-box">
            <div className="inner">
              <div className="bold" style={{ color: "#fff" }}>
                현재 단계 담당
              </div>
              <div className="mt-4">{reference.steps.find((s) => s.n === step)?.owner}</div>
              <div className="mt-8" style={{ color: "#9ca3af" }}>
                ID 발급과 카탈로그 발행은 관리자 권한이 필요합니다.
              </div>
            </div>
          </div>
        </aside>
        <div className="col grow" style={{ gap: 0, minHeight: 0 }}>
          <main className="main">
            <div className="card tight row between wrap" style={{ marginBottom: 14 }}>
              <div className="row wrap">
                <span className="bold">작업 프로세스:</span>
                <Badge tone="info">{p.name}</Badge>
                {p.status === "completed" && <Badge tone="ok">✔ 종료</Badge>}
                {p.status === "trashed" && <Badge tone="err">휴지통</Badge>}
                {p.pub_mode ? <Badge tone="purple">발행 모드</Badge> : <Badge>초안 모드</Badge>}
                <span className="tiny muted">모든 변경은 서버에 즉시 저장됩니다 · 최근 변경 {fmtDateTime(p.updated_at)}</span>
              </div>
              <div className="row">
                <Button size="sm" onClick={() => setLogOpen(true)}>
                  활동 로그
                </Button>
                <Button size="sm" variant="outline" onClick={() => setListOpen(true)}>
                  프로세스 목록 ▾
                </Button>
              </div>
            </div>
            {p.status !== "active" && (
              <div style={{ marginBottom: 14 }}>
                <Banner
                  tone="warn"
                  right={
                    p.status === "completed" && canWrite ? (
                      <Button
                        size="sm"
                        onClick={async () => {
                          try {
                            await api.reopenProcess(pid);
                            await refresh();
                            toast.ok("프로세스를 다시 열었습니다");
                          } catch (e) {
                            toast.error(e);
                          }
                        }}
                      >
                        다시 열기
                      </Button>
                    ) : undefined
                  }
                >
                  {p.status === "completed" ? "종료된 프로세스입니다 — 조회만 할 수 있습니다." : "휴지통에 있는 프로세스입니다 — 프로세스 목록에서 복원할 수 있습니다."}
                </Banner>
              </div>
            )}
            {value.params.from && value.params.from !== step && (
              <div style={{ marginBottom: 14 }}>
                <Banner
                  tone="warn"
                  right={
                    <Button size="sm" variant="dark" onClick={() => go(value.params.from!)}>
                      검증으로 복귀 ↩
                    </Button>
                  }
                >
                  <b>⚠ STEP {value.params.from} 위반 수정 중</b>
                  {value.params.shape ? ` — ${value.params.shape}` : ""} · 보강 후 검증으로 복귀하세요 (수정하면 검증 결과가 자동으로 무효화됩니다)
                </Banner>
              </div>
            )}
            <Outlet />
          </main>
          <div className="bottom-bar">
            <Button disabled={step === 1} onClick={() => go(step - 1)}>
              이전
            </Button>
            <div className="small muted ellipsis">
              STEP {step} · {reference.steps.find((s) => s.n === step)?.label}
              {value.gate(step).done ? " — 완료" : ""}
            </div>
            {step < 8 ? (
              <Button variant="primary" onClick={() => go(step + 1)} title={value.gate(step + 1).can_enter ? "" : value.gate(step + 1).reason}>
                다음 (STEP {step + 1}) →
              </Button>
            ) : (
              <span style={{ width: 120 }} />
            )}
          </div>
        </div>
      </div>
      {listOpen && <ProcessListModal currentId={pid} onClose={() => setListOpen(false)} />}
      {logOpen && <ActivityModal pid={pid} onClose={() => setLogOpen(false)} />}
    </StudioCtx.Provider>
  );
}

function ActivityModal({ pid, onClose }: { pid: number; onClose: () => void }) {
  const q = useQuery({ queryKey: ["process", pid, "activities"], queryFn: () => api.processActivities(pid, 100) });
  return (
    <Modal title="활동 로그 (prov:Activity)" onClose={onClose} wide>
      <QueryState q={q}>
        {q.data && q.data.length === 0 ? (
          <Empty>기록된 활동이 없습니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>Activity ID</th>
                  <th>수행</th>
                  <th>내용</th>
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((a) => (
                  <tr key={a.id}>
                    <td className="nowrap">{fmtDateTime(a.at)}</td>
                    <td className="mono nowrap">{a.code}</td>
                    <td className="nowrap">
                      {a.actor} {a.agent_type === "software" && <Badge>시스템</Badge>}
                    </td>
                    <td>{a.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
    </Modal>
  );
}

function ProcessListModal({ currentId, onClose }: { currentId: number; onClose: () => void }) {
  const { canWrite, isAdmin } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState<"open" | "trashed">("open");
  const q = useQuery({ queryKey: ["processes", tab], queryFn: () => api.processes(tab === "trashed" ? "trashed" : undefined) });
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn();
      toast.ok(msg);
      await qc.invalidateQueries({ queryKey: ["processes"] });
      await qc.invalidateQueries({ queryKey: ["process"] });
    } catch (e) {
      toast.error(e);
    }
  };
  const open = (p: Process) => {
    nav(`/studio/${p.id}/step/${p.current_step}`);
    onClose();
  };
  const create = async () => {
    setBusy(true);
    try {
      const d = await api.createProcess();
      await qc.invalidateQueries({ queryKey: ["processes"] });
      nav(`/studio/${d.process.id}/step/1`);
      onClose();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title="프로세스 목록"
      onClose={onClose}
      wide
      footer={
        <Button variant="primary" busy={busy} disabled={!canWrite} onClick={create}>
          ＋ 새 프로세스
        </Button>
      }
    >
      <div className="tabs">
        <button className={cx("tab", tab === "open" && "on")} onClick={() => setTab("open")}>
          진행 중 · 종료
        </button>
        <button className={cx("tab", tab === "trashed" && "on")} onClick={() => setTab("trashed")}>
          휴지통
        </button>
      </div>
      <QueryState q={q}>
        {(q.data || []).length === 0 ? (
          <Empty>{tab === "trashed" ? "휴지통이 비어 있습니다" : "프로세스가 없습니다"}</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>프로세스</th>
                  <th>상태</th>
                  <th>진행</th>
                  <th>조합</th>
                  <th>최근 변경</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((p) => (
                  <tr key={p.id}>
                    <td>
                      <div className="bold">
                        {p.name} {p.id === currentId && <Badge tone="info">현재</Badge>}
                      </div>
                      <div className="tiny muted ellipsis" style={{ maxWidth: 320 }}>
                        {(p.dataset_names || []).join(" · ") || "조합 없음"}
                      </div>
                    </td>
                    <td>{p.status === "completed" ? <Badge tone="ok">종료</Badge> : p.status === "trashed" ? <Badge tone="err">휴지통</Badge> : <Badge tone="info">진행 중</Badge>}</td>
                    <td className="nowrap">
                      STEP {p.current_step} <span className="muted tiny">· 완료 {(p.steps_done || []).length}/8</span>
                    </td>
                    <td className="num">{p.dataset_count}건</td>
                    <td className="nowrap">{fmtDateTime(p.updated_at)}</td>
                    <td className="nowrap right">
                      {tab === "open" ? (
                        <div className="row" style={{ justifyContent: "flex-end" }}>
                          <Button size="sm" variant="outline" onClick={() => open(p)}>
                            열기
                          </Button>
                          {canWrite && p.id !== currentId && (
                            <ConfirmButton size="sm" confirmLabel="휴지통으로" onConfirm={() => act(() => api.trashProcess(p.id), "휴지통으로 옮겼습니다")}>
                              삭제
                            </ConfirmButton>
                          )}
                        </div>
                      ) : (
                        <div className="row" style={{ justifyContent: "flex-end" }}>
                          {canWrite && (
                            <Button size="sm" onClick={() => act(() => api.restoreProcess(p.id), "복원했습니다")}>
                              복원
                            </Button>
                          )}
                          {isAdmin && (
                            <ConfirmButton size="sm" confirmLabel="영구 삭제 확인" onConfirm={() => act(() => api.purgeProcess(p.id), "영구 삭제했습니다 (카탈로그 발행분은 유지)")}>
                              영구 삭제
                            </ConfirmButton>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
    </Modal>
  );
}
