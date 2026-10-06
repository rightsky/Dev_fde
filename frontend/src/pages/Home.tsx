// 대시보드 홈. 모든 수치는 /dashboard 응답의 실시간 집계다 (고정 수치·기준선 없음).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, useReference } from "../auth";
import type { Activity, Dashboard } from "../types";
import { Badge, Button, Card, Empty, QueryState, fmtDateTime, fmtNum, useToast } from "../ui";

type RecentProcess = Dashboard["recent_processes"][number];

export function HomePage() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api.dashboard() });
  return (
    <div>
      <div className="row between top wrap">
        <div>
          <h1 className="page-title">대시보드 홈</h1>
          <p className="page-sub">
            현재 등록된 원천·프로세스·카탈로그 상태입니다.
            {q.data ? ` 집계 시각 ${fmtDateTime(q.data.now)}` : ""}
          </p>
        </div>
        <Button size="sm" busy={q.isFetching} onClick={() => void q.refetch()}>
          새로고침
        </Button>
      </div>
      <QueryState q={q}>{q.data && <DashboardBody data={q.data} />}</QueryState>
    </div>
  );
}

function DashboardBody({ data }: { data: Dashboard }) {
  const c = data.counts;
  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="grid c4">
        <Kpi to="/assets" label="등록 원천" value={c.assets} sub={`이 중 스트림 ${fmtNum(c.streams)}건`} />
        <Kpi to="/studio" label="진행 중 프로세스" value={c.processes_active} sub={`종료 ${fmtNum(c.processes_completed)}건`} />
        <Kpi to="/catalog" label="카탈로그 발행" value={c.catalog_published} sub="현재 발행 상태 (철회분 제외)" />
        <Kpi to="/admin" label="발행 ID" value={c.minted} sub="민팅 대장에 등록된 ID" />
      </div>
      <WorkflowCard processes={data.recent_processes} />
      <ActivityCard activities={data.recent_activities} total={c.activities} />
      <div className="row wrap">
        <span className="small bold dim">바로 가기</span>
        <Link className="btn" to="/assets">
          파일 업로드
        </Link>
        <Link className="btn" to="/studio">
          스튜디오
        </Link>
        <Link className="btn" to="/catalog">
          카탈로그
        </Link>
      </div>
    </div>
  );
}

// ───────────── 지표 타일
function Kpi({ to, label, value, sub }: { to: string; label: string; value: number; sub: string }) {
  return (
    <Link to={to} className="card accent-top clickable" style={{ display: "block", textDecoration: "none", color: "var(--ink)" }}>
      <div className="row between">
        <span className="stat-label">{label}</span>
        <span className="muted" aria-hidden="true">
          →
        </span>
      </div>
      <div className="stat">{fmtNum(value)}</div>
      <div className="small muted">{sub}</div>
    </Link>
  );
}

// ───────────── 워크플로 진행
function WorkflowCard({ processes }: { processes: RecentProcess[] }) {
  const { canWrite } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    try {
      const d = await api.createProcess();
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
      void qc.invalidateQueries({ queryKey: ["processes"] });
      nav(`/studio/${d.process.id}/step/1`);
    } catch (e) {
      toast.error(e);
      setBusy(false);
    }
  };

  return (
    <Card
      title={
        <>
          워크플로 진행 <span className="small muted">최근 변경 순 {processes.length}건</span>
        </>
      }
      right={
        <Link className="small bold" to="/studio">
          스튜디오 열기 →
        </Link>
      }
    >
      {processes.length === 0 ? (
        <Empty>
          <div>등록된 프로세스가 없습니다.</div>
          {canWrite ? (
            <div className="mt-12">
              <Button variant="primary" busy={busy} onClick={create}>
                새 프로세스 시작
              </Button>
            </div>
          ) : (
            <div className="mt-4">열람 전용 계정은 프로세스를 시작할 수 없습니다.</div>
          )}
        </Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>프로세스</th>
                <th>상태</th>
                <th>8단계 진행</th>
                <th>검증</th>
                <th>최근 변경</th>
              </tr>
            </thead>
            <tbody>
              {processes.map((p) => (
                <ProcessRow key={p.id} p={p} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function ProcessRow({ p }: { p: RecentProcess }) {
  return (
    <tr>
      <td>
        <Link className="bold" to={`/studio/${p.id}/step/${p.current_step}`}>
          {p.name}
        </Link>
        <div className="tiny muted">조합 {fmtNum(p.dataset_count)}건</div>
      </td>
      <td>
        <div className="row wrap gap-4">
          {p.status === "completed" ? <Badge tone="ok">종료</Badge> : p.status === "trashed" ? <Badge tone="err">휴지통</Badge> : <Badge tone="info">진행 중</Badge>}
          {p.pub_mode ? <Badge tone="purple">발행 모드</Badge> : <Badge>초안 모드</Badge>}
        </div>
      </td>
      <td>
        <StepPills p={p} />
        <div className="tiny muted mt-4">
          완료 {p.steps_done.length}/8{p.status === "active" ? ` · 현재 STEP ${p.current_step}` : ""}
        </div>
      </td>
      <td>
        <ValidationSummary v={p.validation} />
      </td>
      <td className="nowrap">{fmtDateTime(p.updated_at)}</td>
    </tr>
  );
}

/** 8단계 알약: 완료 → 초록, 현재(진행 중인 프로세스만) → 파랑, 나머지 → 회색. 현재 단계에는 테두리를 덧댄다. */
function StepPills({ p }: { p: RecentProcess }) {
  const { steps } = useReference();
  const done = new Set(p.steps_done);
  return (
    <div className="row gap-4 wrap">
      {steps.map((s) => {
        const isDone = done.has(s.n);
        const isCurrent = p.status === "active" && p.current_step === s.n;
        const state = isDone ? "완료" : isCurrent ? "현재 단계" : "미완료";
        return (
          <span key={s.n} title={`STEP ${s.n} ${s.label} — ${state}${isDone && isCurrent ? " · 현재 단계" : ""}`} style={isCurrent ? { borderRadius: "var(--r-pill)", outline: "2px solid var(--primary)", outlineOffset: 1 } : undefined}>
            <Badge tone={isDone ? "ok" : isCurrent ? "solid" : "muted"}>
              {isDone ? "✓" : ""}
              {s.n}
            </Badge>
          </span>
        );
      })}
    </div>
  );
}

function ValidationSummary({ v }: { v: RecentProcess["validation"] }) {
  if (v.run_id == null) return <span className="muted">검증 전</span>;
  if (v.stale) {
    return (
      <div>
        <Badge tone="warn" title={v.stale}>
          재검증 필요
        </Badge>
        <div className="tiny muted mt-4">
          직전 검증 통과 {v.pass_count}/{v.total}
        </div>
      </div>
    );
  }
  const allPass = v.total > 0 && v.pass_count === v.total;
  return (
    <div className="row wrap gap-4">
      <Badge tone={allPass ? "ok" : "warn"}>
        검증 통과 {v.pass_count}/{v.total}
      </Badge>
      {v.mode === "publish" && <span className="tiny muted">발행 모드 검증</span>}
    </div>
  );
}

// ───────────── 최근 활동
function ActivityCard({ activities, total }: { activities: Activity[]; total: number }) {
  return (
    <Card
      title="최근 활동"
      right={
        <span className="small muted">
          전체 {fmtNum(total)}건 중 최근 {activities.length}건
        </span>
      }
    >
      {activities.length === 0 ? (
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
              {activities.map((a) => (
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
    </Card>
  );
}
