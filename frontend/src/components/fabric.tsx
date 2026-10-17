// 데이터 패브릭 외부 연계: 연계 현황판(읽기 전용) + 기관 DB 스키마 커넥터
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";
import type { ConnectorKind, DbConnector, IntegrationItem } from "../types";
import { Badge, Banner, Button, ConfirmButton, Empty, Field, Modal, QueryState, fmtDateTime, fmtNum, useToast } from "../ui";

/** 외부 연결 세 곳(Claude API · MCP · DB 커넥터)의 켜짐 여부와 최근 사용. N²SF 통제표 3절과 같은 순서 */
export function IntegrationsBoard() {
  const q = useQuery({ queryKey: ["integrations"], queryFn: api.integrations, refetchInterval: 60_000 });
  return (
    <QueryState q={q}>
      {q.data && (
        <>
          <div className="grid c3">
            {q.data.items.map((it) => (
              <IntegrationTile key={it.key} item={it} />
            ))}
          </div>
          <p className="tiny muted mt-8">
            읽기 전용 현황입니다. 설정은 서버 `.env`(Claude API) · 관리 › AI 에이전트(MCP) · 아래 커넥터 표에서 바꿉니다.
            {q.data.api_docs_exposed && " · 주의: /api/docs 가 열려 있습니다 (운영에서는 FDE_EXPOSE_API_DOCS=false)"}
          </p>
        </>
      )}
    </QueryState>
  );
}

function IntegrationTile({ item }: { item: IntegrationItem }) {
  const tone = item.status === "on" ? "ok" : item.status === "error" ? "err" : "muted";
  const label = item.status === "on" ? "켜짐" : item.status === "error" ? "오류" : "꺼짐";
  return (
    <div className="card" aria-label={item.name}>
      <div className="row between top gap-8">
        <div className="bold">{item.name}</div>
        <Badge tone={tone}>{label}</Badge>
      </div>
      <div className="small dim mt-4">
        <Badge tone={item.direction === "outbound" ? "purple" : "info"}>{item.direction === "outbound" ? "송신" : "수신"}</Badge> {item.detail}
      </div>
      <div className="tiny muted mt-8">{item.scope}</div>
      <div className="tiny muted mt-4">
        최근 사용 {item.last_at ? fmtDateTime(item.last_at) : "없음"}
        {item.today != null && ` · 오늘 ${fmtNum(item.today)}건`}
      </div>
    </div>
  );
}

const STATUS: Record<DbConnector["status"], { label: string; tone: "ok" | "err" | "muted" }> = {
  never: { label: "미시험", tone: "muted" },
  ok: { label: "정상", tone: "ok" },
  error: { label: "오류", tone: "err" },
};

/** 기관 DB 스키마 커넥터 표. 테이블 · 컬럼 · 자료형만 읽어 원천 자산으로 만든다 */
export function ConnectorsPanel({ onSynced }: { onSynced?: () => void }) {
  const { canWrite, isAdmin } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["connectors"], queryFn: api.connectors });
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["connectors"] });
    void qc.invalidateQueries({ queryKey: ["integrations"] });
  };
  const test = async (c: DbConnector) => {
    setBusy(`test-${c.id}`);
    try {
      const r = await api.testConnector(c.id);
      await refresh();
      if (r.ok) toast.ok(`접속 성공 — ${c.name}: 표 ${r.tables}개 · 컬럼 ${r.columns}개`);
      else toast.error(new Error(`접속 실패 — ${r.error}`));
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const sync = async (c: DbConnector) => {
    setBusy(`sync-${c.id}`);
    try {
      const r = await api.syncConnector(c.id);
      await refresh();
      await qc.invalidateQueries({ queryKey: ["assets"] });
      void qc.invalidateQueries({ queryKey: ["process"] });
      toast.ok(`스키마 동기화 — 표 ${r.tables}개 · 새 자산 ${r.created.length} · 갱신 ${r.updated.length}${r.missing.length ? ` · 원천에서 사라진 표 ${r.missing.length}` : ""}`);
      onSynced?.();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const remove = async (c: DbConnector) => {
    setBusy(`del-${c.id}`);
    try {
      await api.deleteConnector(c.id);
      await refresh();
      await qc.invalidateQueries({ queryKey: ["assets"] });
      toast.ok(`커넥터 삭제 — ${c.name} (가져온 자산은 남습니다)`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="row between top wrap mb-8">
        <div>
          <div className="section-title">기관 DB 스키마 커넥터</div>
          <p className="small dim">
            기관 시스템 DB 에 읽기 전용으로 붙어 <b>테이블 · 컬럼 · 자료형만</b> 가져옵니다. 행 데이터 · 예시값 · 통계는 읽지 않으며, 표 하나가 원천 자산 하나가 되어 STEP 1 후보 · 데이터 사전 · 기관 등급표 매칭에 쓰입니다.
            비밀번호는 암호화해 저장하고 화면 · API 어디에도 다시 보이지 않습니다.
          </p>
        </div>
        <Button variant="primary" disabled={!isAdmin} onClick={() => setOpen(true)} title={isAdmin ? "DB 접속 정보를 등록합니다" : "커넥터 등록은 관리자만 할 수 있습니다"}>
          ＋ DB 커넥터 등록
        </Button>
      </div>
      <QueryState q={q}>
        {q.data && q.data.items.length === 0 ? (
          <Empty>등록된 커넥터가 없습니다 — 관리자가 등록하면 담당자가 접속 시험 · 스키마 동기화를 할 수 있습니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>이름</th>
                  <th>종류</th>
                  <th>접속</th>
                  <th>제공기관</th>
                  <th>상태</th>
                  <th className="num">표</th>
                  <th className="num">자산</th>
                  <th>마지막 동기화</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data?.items || []).map((c) => (
                  <tr key={c.id}>
                    <td style={{ minWidth: 140 }}>
                      <div className="bold">{c.name}</div>
                      {c.note && <div className="small dim">{c.note}</div>}
                    </td>
                    <td>
                      <Badge tone="info">{c.kind_label}</Badge>
                    </td>
                    <td className="mono tiny">
                      {c.username}@{c.host}:{c.port}/{c.database}
                      {c.schema && <span className="muted"> · {c.schema}</span>}
                    </td>
                    <td>{c.org?.label || <span className="muted">—</span>}</td>
                    <td>
                      <Badge tone={STATUS[c.status].tone} title={c.last_error || undefined}>
                        {STATUS[c.status].label}
                      </Badge>
                      {c.last_error && <div className="tiny t-err" style={{ maxWidth: 260 }}>{c.last_error}</div>}
                    </td>
                    <td className="num">{c.table_count ? fmtNum(c.table_count) : "—"}</td>
                    <td className="num">{c.asset_count ? fmtNum(c.asset_count) : "—"}</td>
                    <td className="nowrap">{c.last_synced_at ? fmtDateTime(c.last_synced_at) : <span className="muted">없음</span>}</td>
                    <td>
                      <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
                        <Button size="sm" disabled={!canWrite || busy !== null} busy={busy === `test-${c.id}`} onClick={() => test(c)}>
                          접속 시험
                        </Button>
                        <Button size="sm" variant="outline" disabled={!canWrite || busy !== null} busy={busy === `sync-${c.id}`} onClick={() => sync(c)} title="스키마를 읽어 표마다 원천 자산을 만들거나 갱신합니다">
                          스키마 동기화
                        </Button>
                        {isAdmin && (
                          <ConfirmButton size="sm" busy={busy === `del-${c.id}`} onConfirm={() => remove(c)} title="비밀번호는 즉시 폐기되고 가져온 자산은 남습니다">
                            삭제
                          </ConfirmButton>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
      {open && q.data && <ConnectorModal kinds={q.data.kinds} onClose={() => setOpen(false)} onCreated={refresh} />}
    </div>
  );
}

function ConnectorModal({ kinds, onClose, onCreated }: { kinds: ConnectorKind[]; onClose: () => void; onCreated: () => Promise<void> }) {
  const toast = useToast();
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: api.orgs });
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ConnectorKind["kind"]>(kinds[0]?.kind || "postgresql");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("");
  const [database, setDatabase] = useState("");
  const [schema, setSchema] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [orgId, setOrgId] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const k = kinds.find((x) => x.kind === kind);
  const ready = name.trim() && host.trim() && database.trim() && username.trim();

  const save = async () => {
    setBusy(true);
    try {
      const c = await api.createConnector({
        name: name.trim(),
        kind,
        host: host.trim(),
        port: port.trim() ? Number(port) : null,
        database: database.trim(),
        schema: schema.trim() || null,
        username: username.trim(),
        password,
        org_id: orgId ? Number(orgId) : null,
        note: note.trim() || null,
      });
      await onCreated();
      toast.ok(`커넥터 등록 — ${c.name}. 「접속 시험」으로 확인한 뒤 「스키마 동기화」를 누르세요`);
      onClose();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title="DB 커넥터 등록"
      onClose={onClose}
      wide
      footer={
        <>
          <Button onClick={onClose}>취소</Button>
          <Button variant="primary" busy={busy} disabled={!ready} onClick={save}>
            등록
          </Button>
        </>
      }
    >
      <Banner tone="info">읽기 권한만 있는 DB 계정을 쓰세요. 스튜디오는 세션을 읽기 전용으로 열고 스키마 정보(information_schema)만 조회합니다.</Banner>
      <div className="grid c2 mt-12">
        <Field label="커넥터 이름" hint="예: 교통정보시스템 운영 DB">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="DB 종류">
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value as ConnectorKind["kind"])}>
            {kinds.map((x) => (
              <option key={x.kind} value={x.kind}>
                {x.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="호스트" hint="스튜디오 서버에서 닿는 주소 (방화벽 · 보안그룹에서 DB 포트를 열어야 함)">
          <input className="input mono" value={host} onChange={(e) => setHost(e.target.value)} placeholder="10.0.2.15 또는 db.internal" />
        </Field>
        <Field label="포트" hint={`비우면 기본값 ${k?.port ?? ""}`}>
          <input className="input mono" value={port} onChange={(e) => setPort(e.target.value.replace(/[^0-9]/g, ""))} placeholder={String(k?.port ?? "")} />
        </Field>
        <Field label="데이터베이스">
          <input className="input mono" value={database} onChange={(e) => setDatabase(e.target.value)} />
        </Field>
        <Field label="스키마" hint={k?.default_schema ? `비우면 ${k.default_schema}` : "MySQL 은 데이터베이스가 스키마입니다 (비워 둠)"}>
          <input className="input mono" value={schema} onChange={(e) => setSchema(e.target.value)} placeholder={k?.default_schema || ""} />
        </Field>
        <Field label="사용자">
          <input className="input mono" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
        </Field>
        <Field label="비밀번호" hint="암호화해 저장되며 다시 표시되지 않습니다">
          <input className="input mono" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </Field>
        <Field label="제공기관" hint="가져온 표의 제공기관으로 붙습니다">
          <select className="select" value={orgId} onChange={(e) => setOrgId(e.target.value)}>
            <option value="">— 선택 안 함 —</option>
            {(orgs.data || []).filter((o) => o.active).map((o) => (
              <option key={o.id} value={o.id}>
                {o.label} ({o.code})
              </option>
            ))}
          </select>
        </Field>
        <Field label="메모">
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="담당 부서 · 계정 발급 근거 등" />
        </Field>
      </div>
    </Modal>
  );
}
