// 시스템 관리 › AI 에이전트(MCP) — 키 발급·폐기, 호출 이력, 연결 안내 (가이드라인 3.4.5 MCP 연계 관리 원칙, 표 39)
import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { AgentCall, AgentKey } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, ConfirmButton, Empty, Field, Modal, QueryState, fmtDateTime, fmtNum, useToast } from "../ui";

const GRADE_LABEL: Record<string, string> = { O: "O · 공개", S: "S · 민감" };
const STATE: Record<AgentKey["state"], { label: string; tone: "ok" | "warn" | "muted" }> = {
  active: { label: "사용 중", tone: "ok" },
  expired: { label: "만료", tone: "warn" },
  revoked: { label: "폐기", tone: "muted" },
};
const CALL_TONE: Record<AgentCall["status"], "ok" | "warn" | "err"> = { ok: "ok", denied: "warn", error: "err" };
const CALL_LABEL: Record<AgentCall["status"], string> = { ok: "성공", denied: "거부", error: "오류" };

const endpoint = () => `${window.location.origin}/api/mcp`;

export function AgentsTab() {
  const keys = useQuery({ queryKey: ["agent-keys"], queryFn: api.agentKeys });
  const info = useQuery({ queryKey: ["mcp-info"], queryFn: api.mcpInfo });
  const [issuing, setIssuing] = useState(false);
  const [issued, setIssued] = useState<AgentKey | null>(null);
  const [filterKey, setFilterKey] = useState<number | null>(null);
  const active = (keys.data || []).filter((k) => k.state === "active");

  return (
    <div className="col gap-12">
      <Banner tone="info">
        AI 에이전트(Claude 등)가 <b>발행된 카탈로그</b>를 MCP 로 조회합니다. 도구는 모두 <b>읽기 전용</b>이고 데이터 파일 자체는 내주지 않습니다 (메타데이터 · 컬럼 구조 · 데이터
        카드 · 이용조건). 키마다 볼 수 있는 보안등급(N²SF O · S)과 도구를 정하며, <b>C(통제) 등급은 어떤 키로도 열리지 않습니다</b>. 모든 호출은 거부된 것까지 이력에 남고, STEP 8 원칙
        10(MCP 연계 관리)의 증빙으로 쓰입니다.
      </Banner>

      <Card
        title={`에이전트 키 ${keys.data ? `· 사용 중 ${active.length}개` : ""}`}
        right={
          <Button variant="primary" onClick={() => setIssuing(true)}>
            ＋ 키 발급
          </Button>
        }
      >
        <QueryState q={keys}>
          {keys.data && keys.data.length === 0 ? (
            <Empty>발급한 키가 없습니다 — 키가 없으면 어떤 에이전트도 카탈로그에 접근할 수 없습니다</Empty>
          ) : (
            <KeyTable keys={keys.data || []} selected={filterKey} onSelect={(id) => setFilterKey(id === filterKey ? null : id)} />
          )}
        </QueryState>
      </Card>

      <CallLog keyId={filterKey} keys={keys.data || []} onClear={() => setFilterKey(null)} />

      <Card title="연결 방법">
        <ConnectGuide tools={info.data?.tools || []} />
      </Card>

      {issuing && (
        <Modal title="AI 에이전트 키 발급" onClose={() => setIssuing(false)} wide>
          <IssueForm
            tools={info.data?.tools.map((t) => t.name) || []}
            onClose={() => setIssuing(false)}
            onIssued={(k) => {
              setIssuing(false);
              setIssued(k);
            }}
          />
        </Modal>
      )}
      {issued && (
        <Modal title="키가 발급되었습니다" onClose={() => setIssued(null)} wide>
          <IssuedKey k={issued} onClose={() => setIssued(null)} />
        </Modal>
      )}
    </div>
  );
}

function KeyTable({ keys, selected, onSelect }: { keys: AgentKey[]; selected: number | null; onSelect: (id: number) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState<number | null>(null);
  const revoke = async (k: AgentKey) => {
    setBusy(k.id);
    try {
      await api.revokeAgentKey(k.id);
      await qc.invalidateQueries({ queryKey: ["agent-keys"] });
      toast.ok(`키 폐기 — ${k.name}. 이 키를 쓰는 에이전트는 바로 접근이 막힙니다`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>사용처</th>
            <th>키</th>
            <th>접근 등급</th>
            <th>도구</th>
            <th>상태</th>
            <th className="num">최근 30일 호출</th>
            <th>마지막 사용</th>
            <th>만료</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k.id} style={selected === k.id ? { background: "var(--bg)" } : undefined}>
              <td>
                <b>{k.name}</b>
                {k.purpose && <div className="small dim">{k.purpose}</div>}
              </td>
              <td className="mono nowrap">{k.prefix}…</td>
              <td className="nowrap">
                {k.grades.map((g) => (
                  <Badge key={g} tone={g === "O" ? "info" : "purple"}>
                    {GRADE_LABEL[g] || g}
                  </Badge>
                ))}
              </td>
              <td className="small">{k.tools.length >= 6 ? "전체 조회 도구" : k.tools.join(", ")}</td>
              <td>
                <Badge tone={STATE[k.state].tone}>{STATE[k.state].label}</Badge>
              </td>
              <td className="num nowrap">
                {fmtNum(k.stats_30d.ok)}
                {k.stats_30d.denied > 0 && <span className="t-warn"> · 거부 {fmtNum(k.stats_30d.denied)}</span>}
                {k.stats_30d.error > 0 && <span className="t-err"> · 오류 {fmtNum(k.stats_30d.error)}</span>}
                <div className="small dim">하루 상한 {fmtNum(k.daily_limit)}</div>
              </td>
              <td className="nowrap small">{k.last_used_at ? fmtDateTime(k.last_used_at) : <span className="muted">—</span>}</td>
              <td className="nowrap small">{k.revoked_at ? `폐기 ${fmtDateTime(k.revoked_at)}` : k.expires_at ? fmtDateTime(k.expires_at) : "없음"}</td>
              <td className="nowrap">
                <div className="row">
                  <Button size="sm" onClick={() => onSelect(k.id)}>
                    {selected === k.id ? "이력 전체" : "이력"}
                  </Button>
                  {k.state === "active" && (
                    <ConfirmButton size="sm" variant="danger" confirmLabel="정말 폐기" busy={busy === k.id} onConfirm={() => void revoke(k)}>
                      폐기
                    </ConfirmButton>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IssueForm({ tools, onClose, onIssued }: { tools: string[]; onClose: () => void; onIssued: (k: AgentKey) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [grades, setGrades] = useState<string[]>(["O"]);
  const [picked, setPicked] = useState<string[]>(tools);
  const [limit, setLimit] = useState(1000);
  const [days, setDays] = useState("90");
  const [busy, setBusy] = useState(false);
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const valid = name.trim() !== "" && grades.length > 0 && picked.length > 0 && limit >= 1;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      const k = await api.createAgentKey({
        name: name.trim(),
        purpose: purpose.trim() || undefined,
        grades,
        tools: picked,
        daily_limit: limit,
        expires_days: days === "none" ? null : Number(days),
      });
      await qc.invalidateQueries({ queryKey: ["agent-keys"] });
      onIssued(k);
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="col gap-12">
      <div className="grid c2">
        <Field label="사용처" hint="누가 어떤 에이전트로 쓰는지 — 예: 정책분석팀 Claude">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} autoFocus />
        </Field>
        <Field label="이용 목적 (선택)" hint="이력 검토 때 목적에 맞는 호출인지 판단하는 근거가 됩니다">
          <input className="input" value={purpose} onChange={(e) => setPurpose(e.target.value)} maxLength={1000} />
        </Field>
      </div>
      <Field label="접근할 수 있는 보안등급 (N²SF)" hint="최소권한 원칙 — 필요한 등급만 고르세요. 등급을 정하지 않은 데이터셋은 S 로 봅니다. C(통제)는 고를 수 없습니다">
        <div className="row wrap">
          {["O", "S"].map((g) => (
            <label key={g} className="check">
              <input type="checkbox" checked={grades.includes(g)} onChange={() => setGrades(toggle(grades, g))} />
              {GRADE_LABEL[g]}
            </label>
          ))}
          <label className="check muted">
            <input type="checkbox" disabled checked={false} readOnly /> C · 통제 (에이전트 접근 불가)
          </label>
        </div>
      </Field>
      <Field label="쓸 수 있는 도구" hint="모두 읽기 전용 조회 도구입니다">
        <div className="row wrap">
          {tools.map((t) => (
            <label key={t} className="check mono small">
              <input type="checkbox" checked={picked.includes(t)} onChange={() => setPicked(toggle(picked, t))} />
              {t}
            </label>
          ))}
        </div>
      </Field>
      <div className="grid c2">
        <Field label="하루 호출 상한">
          <input className="input" type="number" min={1} max={100000} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
        </Field>
        <Field label="유효 기간">
          <select className="select" value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="30">30일</option>
            <option value="90">90일</option>
            <option value="180">180일</option>
            <option value="365">1년</option>
            <option value="none">만료 없음 (권장하지 않음)</option>
          </select>
        </Field>
      </div>
      <div className="row mt-8" style={{ justifyContent: "flex-end" }}>
        <Button onClick={onClose}>취소</Button>
        <Button type="submit" variant="primary" busy={busy} disabled={!valid}>
          발급
        </Button>
      </div>
    </form>
  );
}

function IssuedKey({ k, onClose }: { k: AgentKey; onClose: () => void }) {
  return (
    <div className="col gap-12">
      <Banner tone="warn">
        이 키는 <b>지금 한 번만</b> 보입니다. 서버에는 키의 해시만 저장되어 다시 볼 수 없습니다. 복사해서 에이전트 설정에 넣으세요. 잃어버리면 폐기하고 새로 발급하면 됩니다.
      </Banner>
      <Field label={`${k.name} — 에이전트 키`}>
        <CodeBlock text={k.key || ""} wrap />
      </Field>
      <ConnectGuide keyText={k.key} tools={[]} />
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <Button variant="primary" onClick={onClose}>
          복사했습니다
        </Button>
      </div>
    </div>
  );
}

function ConnectGuide({ keyText, tools }: { keyText?: string; tools: { name: string; description: string }[] }) {
  const key = keyText || "fde_발급받은_키";
  const url = endpoint();
  const json = JSON.stringify({ mcpServers: { "fde-catalog": { type: "http", url, headers: { Authorization: `Bearer ${key}` } } } }, null, 2);
  return (
    <div className="col gap-12">
      <div className="small">
        주소 <span className="mono">{url}</span> · 방식 Streamable HTTP · 인증 헤더 <span className="mono">Authorization: Bearer fde_…</span>
        <div className="dim">
          다른 컴퓨터의 에이전트가 접속하려면 주소의 localhost 대신 이 서버의 IP 나 도메인을 쓰고, 외부에 열 때는 HTTPS(역방향 프록시) 뒤에 두세요.
        </div>
      </div>
      <Field label="Claude Code — 터미널에서 한 줄로 등록">
        <CodeBlock text={`claude mcp add --transport http fde-catalog ${url} --header "Authorization: Bearer ${key}"`} wrap />
      </Field>
      <Field label="MCP 설정 파일 (.mcp.json 등 HTTP 방식을 지원하는 클라이언트)">
        <CodeBlock text={json} />
      </Field>
      {tools.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>도구</th>
                <th>하는 일</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((t) => (
                <tr key={t.name}>
                  <td className="mono nowrap">{t.name}</td>
                  <td className="small">{t.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CallLog({ keyId, keys, onClear }: { keyId: number | null; keys: AgentKey[]; onClear: () => void }) {
  const [status, setStatus] = useState("");
  const q = useQuery({
    queryKey: ["agent-calls", keyId, status],
    queryFn: () => api.agentCalls({ key_id: keyId ?? undefined, status: status || undefined, limit: 200 }),
  });
  const qc = useQueryClient();
  const keyName = keys.find((k) => k.id === keyId)?.name;
  return (
    <Card
      title={`호출 이력${keyName ? ` — ${keyName}` : ""}`}
      right={
        <div className="row">
          {keyId != null && (
            <Button size="sm" onClick={onClear}>
              전체 키 보기
            </Button>
          )}
          <select className="select" style={{ width: 120 }} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="호출 결과 거르기">
            <option value="">결과 전체</option>
            <option value="ok">성공</option>
            <option value="denied">거부</option>
            <option value="error">오류</option>
          </select>
          <Button
            size="sm"
            busy={q.isFetching}
            onClick={() => {
              void q.refetch();
              void qc.invalidateQueries({ queryKey: ["agent-keys"] });
            }}
          >
            새로 고침
          </Button>
        </div>
      }
    >
      <QueryState q={q}>
        {q.data && q.data.length === 0 ? (
          <Empty>기록된 호출이 없습니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>키</th>
                  <th>도구</th>
                  <th>인자</th>
                  <th>응답에 담긴 데이터셋</th>
                  <th>결과</th>
                  <th className="num">ms</th>
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((c) => (
                  <tr key={c.id}>
                    <td className="nowrap small">{fmtDateTime(c.at)}</td>
                    <td className="small">{c.key_label}</td>
                    <td className="mono nowrap small">{c.tool}</td>
                    <td className="mono small" style={{ maxWidth: 260, wordBreak: "break-all" }}>
                      {Object.entries(c.arguments)
                        .filter(([, v]) => v !== "" && v != null)
                        .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
                        .join(" · ") || "—"}
                    </td>
                    <td className="mono small">{c.resource_ids.length ? c.resource_ids.slice(0, 5).join(", ") + (c.resource_ids.length > 5 ? ` 외 ${c.resource_ids.length - 5}` : "") : "—"}</td>
                    <td>
                      <Badge tone={CALL_TONE[c.status]} title={c.message || undefined}>
                        {CALL_LABEL[c.status]}
                      </Badge>
                      {c.message && <div className="small dim">{c.message}</div>}
                    </td>
                    <td className="num small">{c.duration_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
    </Card>
  );
}
