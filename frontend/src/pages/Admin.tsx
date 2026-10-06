// 시스템 관리 — 사용자 · 기관 · 분류체계 · 민팅 대장 · 활동 로그 · 셰이프
import { useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth, useReference } from "../auth";
import type { Org, Role, TaxAxis, TaxCode, User } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, ConfirmButton, Empty, Field, Modal, QueryState, SeverityBadge, Tabs, cx, fmtDateTime, fmtNum, useToast } from "../ui";

const TABS = [
  { key: "users", label: "사용자" },
  { key: "orgs", label: "기관" },
  { key: "taxonomy", label: "분류체계" },
  { key: "mint", label: "민팅 대장" },
  { key: "activity", label: "활동 로그" },
  { key: "shapes", label: "셰이프" },
] as const;
type TabKey = (typeof TABS)[number]["key"];
const isTab = (v: string | null): v is TabKey => TABS.some((t) => t.key === v);

/** 변경 동작 공통: 진행 중인 동작의 키를 들고 있고, 실패하면 서버 문구를 토스트로 보여 준다. 성공 여부를 돌려준다. */
function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const run = async (key: string, fn: () => Promise<string>): Promise<boolean> => {
    setBusy(key);
    try {
      toast.ok(await fn());
      return true;
    } catch (e) {
      toast.error(e);
      return false;
    } finally {
      setBusy(null);
    }
  };
  return { busy, run };
}

/** 대화상자 본문 아래의 버튼 줄.
 *  입력 상태는 Modal 을 그리는 컴포넌트가 아니라 본문 컴포넌트에 두고 버튼도 본문에 둔다 — 공용 Modal 은 다시 그려질 때마다
 *  대화상자로 포커스를 옮기므로, 상태를 바깥에 두면 한 글자 칠 때마다 입력란이 포커스를 잃는다. */
function FormActions({ children }: { children: ReactNode }) {
  return (
    <div className="row mt-16" style={{ justifyContent: "flex-end" }}>
      {children}
    </div>
  );
}

const dash = <span className="muted">—</span>;

export function AdminPage() {
  const { isAdmin, canWrite, user } = useAuth();
  const ref = useReference();
  const [sp, setSp] = useSearchParams();
  const raw = sp.get("tab");
  const tab: TabKey = isTab(raw) ? raw : isAdmin ? "users" : "orgs";
  const roleLabel = ref.roles.find((r) => r.value === user.role)?.label || user.role;

  return (
    <div>
      <h1 className="page-title">시스템 관리</h1>
      <p className="page-sub">계정과 권한, 기관 · 분류체계 같은 통제 어휘, 발행 ID 대장, 활동 이력, 검증 셰이프를 한곳에서 봅니다.</p>
      {!isAdmin && (
        <div className="mb-8">
          <Banner tone="info">
            {roleLabel} 계정입니다 — 사용자 관리와 설정 변경은 관리자만 할 수 있고, 나머지 탭은 조회할 수 있습니다.{canWrite ? " 기관 등록은 담당자도 할 수 있습니다." : ""}
          </Banner>
        </div>
      )}
      <Tabs tabs={[...TABS]} value={tab} onChange={(k) => setSp({ tab: k })} />
      {tab === "users" && <UsersTab />}
      {tab === "orgs" && <OrgsTab />}
      {tab === "taxonomy" && <TaxonomyTab />}
      {tab === "mint" && <MintTab />}
      {tab === "activity" && <ActivityTab />}
      {tab === "shapes" && <ShapesTab />}
    </div>
  );
}

// ───────────── 사용자
const USERNAME_RE = /^[A-Za-z0-9._-]{3,60}$/;
const MIN_PASSWORD = 8;

function UsersTab() {
  const { isAdmin } = useAuth();
  if (!isAdmin) {
    return (
      <div className="col gap-12">
        <Banner tone="warn">관리자 권한이 필요합니다 — 사용자 목록과 계정 관리는 관리자만 볼 수 있습니다.</Banner>
        <RoleGuide />
      </div>
    );
  }
  return <UsersAdmin />;
}

/** 역할별 설명 (참조 데이터). 사용자 목록이 있으면 역할별 인원도 함께 보여 준다. */
function RoleGuide({ users }: { users?: User[] }) {
  const ref = useReference();
  return (
    <div className="grid c3">
      {ref.roles.map((r) => (
        <div key={r.value} className="card tight flat">
          <div className="row between">
            <span className="row gap-4">
              <b>{r.label}</b>
              <span className="kbd">{r.value}</span>
            </span>
            {users && <span className="small dim">{fmtNum(users.filter((u) => u.role === r.value).length)}명</span>}
          </div>
          <div className="small dim mt-4">{r.desc}</div>
        </div>
      ))}
    </div>
  );
}

function UsersAdmin() {
  const { user: me } = useAuth();
  const ref = useReference();
  const qc = useQueryClient();
  const { busy, run } = useAction();
  const q = useQuery({ queryKey: ["users"], queryFn: api.users });
  const [adding, setAdding] = useState(false);
  const [pwFor, setPwFor] = useState<User | null>(null);

  const update = (u: User, key: string, body: { role?: Role; active?: boolean }, done: string) =>
    run(`${key}:${u.id}`, async () => {
      await api.updateUser(u.id, body);
      await qc.invalidateQueries({ queryKey: ["users"] });
      return done;
    });
  const roleLabel = (role: Role) => ref.roles.find((r) => r.value === role)?.label || role;

  return (
    <div className="col gap-12">
      <RoleGuide users={q.data} />
      <div className="row between wrap">
        <div className="small dim">
          {q.data && (
            <>
              전체 <b>{fmtNum(q.data.length)}명</b> · 활성 {fmtNum(q.data.filter((u) => u.active).length)}명 · 비활성 {fmtNum(q.data.filter((u) => !u.active).length)}명
            </>
          )}
        </div>
        <Button variant="primary" onClick={() => setAdding(true)}>
          ＋ 사용자 추가
        </Button>
      </div>
      <QueryState q={q}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>이름</th>
                <th>역할</th>
                <th>소속</th>
                <th>이메일</th>
                <th>상태</th>
                <th>등록일</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(q.data || []).map((u) => (
                <tr key={u.id} className={cx(!u.active && "muted")}>
                  <td className="mono bold nowrap">
                    {u.username} {u.id === me.id && <Badge tone="info">나</Badge>}
                  </td>
                  <td>{u.name}</td>
                  <td>
                    <select
                      className="select"
                      style={{ width: 120 }}
                      value={u.role}
                      disabled={busy === `role:${u.id}`}
                      aria-label={`${u.name} 역할`}
                      onChange={(e) => {
                        const next = ref.roles.find((r) => r.value === e.target.value);
                        if (next && next.value !== u.role) void update(u, "role", { role: next.value }, `역할 변경 — ${u.name}: ${roleLabel(u.role)} → ${next.label}`);
                      }}
                    >
                      {ref.roles.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{u.org_label || dash}</td>
                  <td>{u.email || dash}</td>
                  <td>{u.active ? <Badge tone="ok">활성</Badge> : <Badge>비활성</Badge>}</td>
                  <td className="nowrap">{fmtDateTime(u.created_at)}</td>
                  <td>
                    <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
                      {u.active ? (
                        <ConfirmButton size="sm" busy={busy === `active:${u.id}`} onConfirm={() => void update(u, "active", { active: false }, `계정 비활성화 — ${u.name}`)}>
                          비활성화
                        </ConfirmButton>
                      ) : (
                        <Button size="sm" variant="ok" busy={busy === `active:${u.id}`} onClick={() => void update(u, "active", { active: true }, `계정 활성화 — ${u.name}`)}>
                          활성화
                        </Button>
                      )}
                      <Button size="sm" onClick={() => setPwFor(u)}>
                        비밀번호 재설정
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </QueryState>
      <p className="tiny muted">비활성 계정은 로그인할 수 없습니다. 자기 자신의 관리자 권한 해제와 비활성화는 서버가 받지 않습니다.</p>

      {adding && (
        <Modal title="사용자 추가" onClose={() => setAdding(false)}>
          <AddUserForm onClose={() => setAdding(false)} />
        </Modal>
      )}
      {pwFor && (
        <Modal title={`비밀번호 재설정 — ${pwFor.name} (${pwFor.username})`} onClose={() => setPwFor(null)}>
          <PasswordForm user={pwFor} onClose={() => setPwFor(null)} />
        </Modal>
      )}
    </div>
  );
}

function AddUserForm({ onClose }: { onClose: () => void }) {
  const ref = useReference();
  const qc = useQueryClient();
  const { busy, run } = useAction();
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("worker");
  const [org, setOrg] = useState("");
  const [email, setEmail] = useState("");

  const usernameOk = USERNAME_RE.test(username);
  const passwordOk = password.length >= MIN_PASSWORD;
  const valid = usernameOk && name.trim() !== "" && passwordOk;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    const ok = await run("create", async () => {
      const u = await api.createUser({ username, name: name.trim(), password, role, org_label: org.trim() || undefined, email: email.trim() || undefined });
      await qc.invalidateQueries({ queryKey: ["users"] });
      return `사용자 추가 — ${u.name} (${u.username})`;
    });
    if (ok) onClose();
  };

  return (
    <form onSubmit={submit}>
      <div className="grid c2">
        <Field label="ID" hint={<span className={cx(username !== "" && !usernameOk && "t-err")}>영문 · 숫자 · . _ - 만, 3자 이상</span>}>
          <input className="input mono" value={username} onChange={(e) => setUsername(e.target.value)} maxLength={60} autoComplete="off" autoFocus />
        </Field>
        <Field label="이름">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} autoComplete="off" />
        </Field>
        <Field label="비밀번호" hint={<span className={cx(password !== "" && !passwordOk && "t-err")}>{MIN_PASSWORD}자 이상 — 첫 로그인 뒤 본인이 바꿀 수 있습니다</span>}>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </Field>
        <Field label="역할" hint={ref.roles.find((r) => r.value === role)?.desc}>
          <select
            className="select"
            value={role}
            onChange={(e) => {
              const next = ref.roles.find((r) => r.value === e.target.value);
              if (next) setRole(next.value);
            }}
          >
            {ref.roles.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label} ({r.value})
              </option>
            ))}
          </select>
        </Field>
        <Field label="소속 (선택)">
          <input className="input" value={org} onChange={(e) => setOrg(e.target.value)} />
        </Field>
        <Field label="이메일 (선택)">
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
        </Field>
      </div>
      <FormActions>
        <Button onClick={onClose}>취소</Button>
        <Button type="submit" variant="primary" busy={busy === "create"} disabled={!valid}>
          추가
        </Button>
      </FormActions>
    </form>
  );
}

function PasswordForm({ user, onClose }: { user: User; onClose: () => void }) {
  const { busy, run } = useAction();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const longEnough = password.length >= MIN_PASSWORD;
  const same = password === again;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!longEnough || !same) return;
    const ok = await run("password", async () => {
      await api.updateUser(user.id, { password });
      return `비밀번호 재설정 — ${user.name}`;
    });
    if (ok) onClose();
  };

  return (
    <form onSubmit={submit}>
      <p className="small muted mb-8">새 비밀번호는 저장하는 즉시 적용됩니다. 기존 비밀번호로는 더 이상 로그인할 수 없으니 당사자에게 따로 알려 주세요.</p>
      <div className="col gap-12">
        <Field label="새 비밀번호" hint={<span className={cx(password !== "" && !longEnough && "t-err")}>{MIN_PASSWORD}자 이상</span>}>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" autoFocus />
        </Field>
        <Field label="새 비밀번호 확인" hint={again !== "" && !same ? <span className="t-err">두 입력이 다릅니다</span> : undefined}>
          <input className="input" type="password" value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" />
        </Field>
      </div>
      <FormActions>
        <Button onClick={onClose}>취소</Button>
        <Button type="submit" variant="primary" busy={busy === "password"} disabled={!longEnough || !same}>
          재설정
        </Button>
      </FormActions>
    </form>
  );
}

// ───────────── 기관
const ORG_CODE_RE = /^ORG-[A-Za-z0-9]{3,20}$/;

function OrgsTab() {
  const { isAdmin, canWrite } = useAuth();
  const q = useQuery({ queryKey: ["orgs"], queryFn: api.orgs });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Org | null>(null);

  return (
    <div className="col gap-12">
      <div className="row between wrap">
        <div className="small dim">
          {q.data && (
            <>
              기관 <b>{fmtNum(q.data.length)}곳</b> · 사용 {fmtNum(q.data.filter((o) => o.active).length)}곳 — 제공기관(dcterms:publisher) 선택지로 쓰입니다
            </>
          )}
        </div>
        {canWrite && (
          <Button variant="primary" onClick={() => setCreating(true)}>
            ＋ 기관 등록
          </Button>
        )}
      </div>
      <QueryState q={q}>
        {q.data && q.data.length === 0 ? (
          <Empty>등록된 기관이 없습니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>코드</th>
                  <th>이름</th>
                  <th>IRI</th>
                  <th>메모</th>
                  <th>상태</th>
                  {isAdmin && <th />}
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((o) => (
                  <tr key={o.id} className={cx(!o.active && "muted")}>
                    <td className="mono bold nowrap">{o.code}</td>
                    <td>{o.label}</td>
                    <td className="mono small">{o.iri}</td>
                    <td>{o.note || dash}</td>
                    <td>{o.active ? <Badge tone="ok">사용</Badge> : <Badge>사용 중지</Badge>}</td>
                    {isAdmin && (
                      <td className="right">
                        <Button size="sm" onClick={() => setEditing(o)}>
                          수정
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>

      {creating && (
        <Modal title="기관 등록" onClose={() => setCreating(false)}>
          <OrgCreateForm onClose={() => setCreating(false)} />
        </Modal>
      )}
      {editing && (
        <Modal title={`기관 수정 — ${editing.code}`} onClose={() => setEditing(null)}>
          <OrgEditForm org={editing} onClose={() => setEditing(null)} />
        </Modal>
      )}
    </div>
  );
}

/** 기관이 바뀌면 기관 이름을 품고 있는 원천 목록과 활동 로그도 다시 불러온다 */
function useOrgRefresh() {
  const qc = useQueryClient();
  return async () => {
    await qc.invalidateQueries({ queryKey: ["orgs"] });
    void qc.invalidateQueries({ queryKey: ["assets"] });
    void qc.invalidateQueries({ queryKey: ["activities"] });
  };
}

function OrgCreateForm({ onClose }: { onClose: () => void }) {
  const refresh = useOrgRefresh();
  const { busy, run } = useAction();
  const [label, setLabel] = useState("");
  const [code, setCode] = useState("");
  const [note, setNote] = useState("");
  const codeOk = code.trim() === "" || ORG_CODE_RE.test(code.trim());
  const valid = label.trim() !== "" && codeOk;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    const ok = await run("create", async () => {
      const o = await api.createOrg({ label: label.trim(), code: code.trim() || undefined, note: note.trim() || undefined });
      await refresh();
      return `기관 등록 — ${o.label} (${o.code})`;
    });
    if (ok) onClose();
  };

  return (
    <form onSubmit={submit}>
      <div className="col gap-12">
        <Field label="이름">
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={200} autoFocus />
        </Field>
        <Field
          label="코드 (선택)"
          hint={codeOk ? "비우면 로컬 코드가 자동 채번됩니다 · 행정표준코드가 있으면 ORG-영숫자 형식으로 적습니다 (예: ORG-1613000)" : <span className="t-err">ORG- 뒤에 영문 · 숫자 3~20자 형식이어야 합니다</span>}
        >
          <input className="input mono" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ORG-" />
        </Field>
        <Field label="메모 (선택)">
          <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
      <FormActions>
        <Button onClick={onClose}>취소</Button>
        <Button type="submit" variant="primary" busy={busy === "create"} disabled={!valid}>
          등록
        </Button>
      </FormActions>
    </form>
  );
}

function OrgEditForm({ org, onClose }: { org: Org; onClose: () => void }) {
  const refresh = useOrgRefresh();
  const { busy, run } = useAction();
  const [label, setLabel] = useState(org.label);
  const [note, setNote] = useState(org.note || "");
  const [active, setActive] = useState(org.active);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (label.trim() === "") return;
    const ok = await run("save", async () => {
      const o = await api.updateOrg(org.id, { label: label.trim(), note: note.trim() || null, active });
      await refresh();
      return `기관 수정 — ${o.label} (${o.code})`;
    });
    if (ok) onClose();
  };

  return (
    <form onSubmit={submit}>
      <div className="col gap-12">
        <Field label="코드" hint="코드는 기관 IRI 에 쓰이므로 바꿀 수 없습니다">
          <input className="input mono" value={org.code} disabled />
        </Field>
        <Field label="이름">
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={200} />
        </Field>
        <Field label="메모">
          <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <label className="check">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          사용 — 끄면 새로 고르는 선택지에서 빠집니다 (이미 지정된 곳은 그대로 유지)
        </label>
      </div>
      <FormActions>
        <Button onClick={onClose}>취소</Button>
        <Button type="submit" variant="primary" busy={busy === "save"} disabled={label.trim() === ""}>
          저장
        </Button>
      </FormActions>
    </form>
  );
}

// ───────────── 분류체계
/** 서버가 코드 추가를 받지 않는 축 (연계키 · 보안등급) */
const FIXED_AXES = ["K", "N2SF"];
const NATURE_TONE: Record<TaxAxis["nature"], "dark" | "info" | "muted"> = { 필수: "dark", 권장: "info", 보조: "muted" };

function TaxonomyTab() {
  const { isAdmin } = useAuth();
  const q = useQuery({ queryKey: ["taxonomy"], queryFn: api.taxonomy });
  const [only, setOnly] = useState("");
  const axes = (q.data || []).filter((a) => !only || a.code === only);

  return (
    <div className="col gap-12">
      <Banner tone="info">폐기한 코드는 새 배정에서 빠지며 이미 발행된 항목은 그대로 유지됩니다.{isAdmin ? "" : " 코드 추가 · 수정 · 폐기는 관리자만 할 수 있습니다."}</Banner>
      <QueryState q={q}>
        <div className="row wrap">
          <button className={cx("chip", only === "" && "on")} aria-pressed={only === ""} onClick={() => setOnly("")}>
            전체 축
          </button>
          {(q.data || []).map((a) => (
            <button key={a.code} className={cx("chip", only === a.code && "on")} aria-pressed={only === a.code} onClick={() => setOnly(a.code)}>
              {a.code} {a.name}
              <span className="score">{a.codes.filter((c) => c.active).length}</span>
            </button>
          ))}
        </div>
        {axes.map((a) => (
          <AxisCard key={a.code} axis={a} isAdmin={isAdmin} />
        ))}
      </QueryState>
    </div>
  );
}

function AxisCard({ axis, isAdmin }: { axis: TaxAxis; isAdmin: boolean }) {
  const qc = useQueryClient();
  const { busy, run } = useAction();
  const [adding, setAdding] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const fixed = FIXED_AXES.includes(axis.code);
  const retired = axis.codes.filter((c) => !c.active).length;

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ["taxonomy"] });
    void qc.invalidateQueries({ queryKey: ["activities"] });
  };
  const add = async (label: string, definition: string) => {
    const ok = await run("add", async () => {
      await api.addTaxCode(axis.code, { label, definition: definition || undefined });
      await refresh();
      return `코드 추가 — ${axis.code} ${axis.name}: ${label}`;
    });
    if (ok) setAdding(false);
  };
  const save = async (c: TaxCode, label: string, definition: string) => {
    const ok = await run(`edit:${c.id}`, async () => {
      await api.updateTaxCode(c.id, { label, definition: definition || null, active: c.active });
      await refresh();
      return `코드 수정 — ${c.code} ${label}`;
    });
    if (ok) setEditId(null);
  };
  const toggle = (c: TaxCode) =>
    run(`toggle:${c.id}`, async () => {
      await api.updateTaxCode(c.id, { label: c.label, definition: c.definition, active: !c.active });
      await refresh();
      return `${c.active ? "코드 폐기" : "코드 복원"} — ${c.code} ${c.label}`;
    });

  return (
    <Card
      title={
        <>
          <span className="mono">{axis.code}</span> {axis.name}
          <Badge tone={NATURE_TONE[axis.nature]}>{axis.nature}</Badge>
          <Badge>{axis.multi ? "다중 선택" : "단일 선택"}</Badge>
          {axis.version && <Badge>{axis.version}</Badge>}
        </>
      }
      right={
        <div className="row">
          <span className="small muted">
            코드 {fmtNum(axis.codes.length)}개{retired > 0 ? ` · 폐기 ${fmtNum(retired)}개` : ""}
          </span>
          {fixed ? (
            <Badge title="연계키 · 보안등급 축은 코드를 추가할 수 없습니다">코드 체계 고정</Badge>
          ) : (
            isAdmin &&
            !adding && (
              <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
                ＋ 코드 추가
              </Button>
            )
          )}
        </div>
      }
    >
      {axis.description && <p className="small dim">{axis.description}</p>}
      <div className="row wrap small mt-4 mb-8">
        <span className="muted">RDF 속성</span>
        {axis.rdf_property ? <span className="kbd">{axis.rdf_property}</span> : dash}
        <span className="muted">스킴</span>
        <span className="mono tiny muted">{axis.scheme_iri}</span>
      </div>
      {adding && <CodeAddForm busy={busy === "add"} onAdd={add} onCancel={() => setAdding(false)} />}
      {axis.codes.length === 0 ? (
        <Empty>이 축에는 아직 코드가 없습니다</Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 96 }}>코드</th>
                <th style={{ width: "26%" }}>라벨</th>
                <th>정의</th>
                <th style={{ width: 72 }}>상태</th>
                {isAdmin && <th style={{ width: 132 }} />}
              </tr>
            </thead>
            <tbody>
              {axis.codes.map((c) =>
                editId === c.id ? (
                  <CodeEditRow key={c.id} code={c} busy={busy === `edit:${c.id}`} onSave={(label, definition) => save(c, label, definition)} onCancel={() => setEditId(null)} />
                ) : (
                  <tr key={c.id} className={cx(!c.active && "muted")}>
                    <td className="mono bold nowrap" title={c.iri}>
                      {c.code}
                    </td>
                    <td>{c.label}</td>
                    <td>
                      {c.definition || (Object.keys(c.extra).length === 0 && dash)}
                      {Object.entries(c.extra).map(([k, v]) => (
                        <span key={k} className="kbd" style={{ marginLeft: c.definition ? 6 : 0, marginRight: 4 }}>
                          {k}: {String(v)}
                        </span>
                      ))}
                    </td>
                    <td>{c.active ? <Badge tone="ok">사용</Badge> : <Badge>폐기</Badge>}</td>
                    {isAdmin && (
                      <td>
                        <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
                          <Button size="sm" onClick={() => setEditId(c.id)}>
                            수정
                          </Button>
                          {c.active ? (
                            <ConfirmButton size="sm" busy={busy === `toggle:${c.id}`} onConfirm={() => void toggle(c)}>
                              폐기
                            </ConfirmButton>
                          ) : (
                            <Button size="sm" variant="ok" busy={busy === `toggle:${c.id}`} onClick={() => void toggle(c)}>
                              복원
                            </Button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function CodeAddForm(props: { busy: boolean; onAdd: (label: string, definition: string) => void; onCancel: () => void }) {
  const [label, setLabel] = useState("");
  const [definition, setDefinition] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (label.trim()) props.onAdd(label.trim(), definition.trim());
  };
  return (
    <form className="card tight flat mb-8" onSubmit={submit}>
      <div className="row wrap top">
        <Field label="라벨" style={{ width: 220 }}>
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={100} autoFocus />
        </Field>
        <Field label="정의 (선택)" style={{ flex: 1, minWidth: 220 }}>
          <input className="input" value={definition} onChange={(e) => setDefinition(e.target.value)} />
        </Field>
        <div className="row" style={{ alignSelf: "flex-end" }}>
          <Button type="submit" variant="primary" busy={props.busy} disabled={!label.trim()}>
            추가
          </Button>
          <Button onClick={props.onCancel}>취소</Button>
        </div>
      </div>
      <div className="hint mt-4">코드 번호는 서버가 이 축의 마지막 번호에 이어서 붙입니다. 같은 라벨은 한 축에 한 번만 쓸 수 있습니다.</div>
    </form>
  );
}

function CodeEditRow(props: { code: TaxCode; busy: boolean; onSave: (label: string, definition: string) => void; onCancel: () => void }) {
  const c = props.code;
  const [label, setLabel] = useState(c.label);
  const [definition, setDefinition] = useState(c.definition || "");
  const save = () => {
    if (label.trim()) props.onSave(label.trim(), definition.trim());
  };
  const onKey = (e: { key: string }) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") props.onCancel();
  };
  return (
    <tr>
      <td className="mono bold nowrap">{c.code}</td>
      <td>
        <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} onKeyDown={onKey} maxLength={100} aria-label={`${c.code} 라벨`} autoFocus />
      </td>
      <td>
        <input className="input" value={definition} onChange={(e) => setDefinition(e.target.value)} onKeyDown={onKey} aria-label={`${c.code} 정의`} placeholder="정의 (선택)" />
      </td>
      <td>{c.active ? <Badge tone="ok">사용</Badge> : <Badge>폐기</Badge>}</td>
      <td>
        <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
          <Button size="sm" variant="primary" busy={props.busy} disabled={!label.trim()} onClick={save}>
            저장
          </Button>
          <Button size="sm" onClick={props.onCancel}>
            취소
          </Button>
        </div>
      </td>
    </tr>
  );
}

// ───────────── 민팅 대장
function MintTab() {
  const q = useQuery({ queryKey: ["mintRegistry"], queryFn: api.mintRegistry });
  const d = q.data;
  return (
    <QueryState q={q}>
      {d && (
        <div className="col gap-12">
          <div className="grid side">
            <Card title="민팅 정책">
              <dl className="kv">
                <dt>작업 중 ID</dt>
                <dd className="mono">{d.policy.draft_pattern}</dd>
                <dt>발행 ID</dt>
                <dd className="mono">{d.policy.published_pattern}</dd>
                <dt>배포본 ID</dt>
                <dd className="mono">{d.policy.distribution_pattern}</dd>
                <dt>Activity ID</dt>
                <dd className="mono">{d.policy.activity_pattern}</dd>
                <dt>IRI 기준 주소</dt>
                <dd className="mono">{d.policy.iri_base}</dd>
              </dl>
              <hr className="divider" />
              <p className="small dim">{d.policy.rule}</p>
            </Card>
            <Card title="다음 발급 번호">
              <div className="grid c2">
                <div>
                  <div className="stat mono">{d.next.DST}</div>
                  <div className="stat-label">데이터셋 (DST)</div>
                </div>
                <div>
                  <div className="stat mono">{d.next.SVC}</div>
                  <div className="stat-label">스트림 · 데이터 서비스 (SVC)</div>
                </div>
              </div>
              <hr className="divider" />
              <p className="small muted">
                발행 ID 발급은 이 화면이 아니라 <Link to="/studio">스튜디오</Link> STEP 6 에서 관리자가 실행합니다. 발급된 번호는 아래 대장에 쌓이고 다시 쓰이지 않습니다.
              </p>
            </Card>
          </div>
          <div>
            <div className="section-title">
              발급 기록 <span className="small muted">{fmtNum(d.records.length)}건</span>
            </div>
            {d.records.length === 0 ? (
              <Empty>발급된 발행 ID 가 없습니다 — 스튜디오 STEP 6 에서 관리자가 발급하면 여기에 기록됩니다</Empty>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>발행 ID</th>
                      <th>종류</th>
                      <th>원천</th>
                      <th>IRI</th>
                      <th>발급 시각</th>
                      <th>비고</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.records.map((r) => (
                      <tr key={r.id}>
                        <td className="mono bold nowrap">{r.minted_id}</td>
                        <td>
                          <Badge tone={r.kind === "SVC" ? "purple" : "info"}>{r.kind}</Badge>
                        </td>
                        <td>{r.asset_name || <span className="muted">원천 #{r.asset_id}</span>}</td>
                        <td className="mono small">{r.iri}</td>
                        <td className="nowrap">{fmtDateTime(r.minted_at)}</td>
                        <td>
                          {r.note || (r.process_id == null && dash)}
                          {r.process_id != null && (
                            <>
                              {" "}
                              <Link className="small nowrap" to={`/studio/${r.process_id}`}>
                                프로세스 열기 →
                              </Link>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </QueryState>
  );
}

// ───────────── 활동 로그
const ACTIVITY_LIMIT = 200;

function ActivityTab() {
  const q = useQuery({ queryKey: ["activities"], queryFn: () => api.activities({ limit: ACTIVITY_LIMIT }) });
  const [text, setText] = useState("");
  const rows = useMemo(() => {
    const all = q.data || [];
    const terms = text.toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return all;
    return all.filter((a) => {
      const hay = `${a.code} ${a.type} ${a.text} ${a.actor}`.toLowerCase();
      return terms.every((t) => hay.includes(t));
    });
  }, [q.data, text]);

  return (
    <div className="col gap-12">
      <div className="row between wrap">
        <div className="row wrap">
          <input
            className="input"
            style={{ width: 280 }}
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="내용 · 유형 · 수행 주체 · ID 로 거르기"
            aria-label="활동 로그 거르기"
          />
          {q.data && (
            <span className="small dim">
              <b>{fmtNum(rows.length)}건</b> 표시 · 불러온 {fmtNum(q.data.length)}건
              {q.data.length >= ACTIVITY_LIMIT ? ` (최근 ${ACTIVITY_LIMIT}건까지만 불러옵니다)` : ""}
            </span>
          )}
        </div>
        <Button size="sm" busy={q.isFetching} onClick={() => void q.refetch()}>
          새로 고침
        </Button>
      </div>
      <QueryState q={q}>
        {rows.length === 0 ? (
          <Empty>{q.data && q.data.length > 0 ? "조건에 맞는 활동이 없습니다" : "기록된 활동이 없습니다"}</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>Activity ID</th>
                  <th>수행</th>
                  <th>유형</th>
                  <th>내용</th>
                  <th>프로세스</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td className="nowrap">{fmtDateTime(a.at)}</td>
                    <td className="mono nowrap" title={a.iri}>
                      {a.code}
                    </td>
                    <td className="nowrap">
                      {a.actor} {a.agent_type === "software" && <Badge tone="purple">시스템</Badge>}
                    </td>
                    <td>
                      <span className="kbd nowrap">{a.type}</span>
                    </td>
                    <td>{a.text}</td>
                    <td className="nowrap">{a.process_id != null ? <Link to={`/studio/${a.process_id}`}>프로세스 #{a.process_id}</Link> : dash}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
    </div>
  );
}

// ───────────── 셰이프
type ShapeMode = "draft" | "publish";
const SHAPE_MODES: { key: ShapeMode; label: string; desc: string }[] = [
  { key: "draft", label: "공통 (draft)", desc: "작업 중 검증에 쓰는 공통 프로파일" },
  { key: "publish", label: "발행 (publish)", desc: "공통 프로파일에 발행 전용 규칙을 더한 프로파일" },
];

function ShapesTab() {
  const [mode, setMode] = useState<ShapeMode>("draft");
  const q = useQuery({ queryKey: ["shapes", mode], queryFn: () => api.shapes(mode), placeholderData: keepPreviousData });
  const d = q.data;
  const rules = d?.rules || [];
  const publishOnly = rules.filter((r) => r.profile === "publish").length;

  return (
    <div className="col gap-12">
      <div className="row between wrap">
        <div className="row wrap">
          {SHAPE_MODES.map((m) => (
            <button key={m.key} className={cx("chip", mode === m.key && "on")} aria-pressed={mode === m.key} title={m.desc} onClick={() => setMode(m.key)}>
              {m.label}
            </button>
          ))}
          {q.isFetching && <span className="spinner" aria-label="불러오는 중" />}
        </div>
        {d && (
          <div className="row wrap small dim">
            <Badge tone="dark">셰이프 버전 {d.version}</Badge>
            <span>
              규칙 {fmtNum(rules.length)}개 — 공통 {fmtNum(rules.length - publishOnly)} · 발행 전용 {fmtNum(publishOnly)}
            </span>
          </div>
        )}
      </div>
      <QueryState q={q}>
        {d && (
          <>
            <Card title="등재 규칙" right={<span className="small muted">위반하면 「수정 경로」의 스튜디오 화면에서 고칩니다</span>}>
              {rules.length === 0 ? (
                <Empty>등재된 규칙이 없습니다</Empty>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>이름</th>
                        <th>심각도</th>
                        <th>경로</th>
                        <th>메시지</th>
                        <th>수정 경로</th>
                        <th>프로파일</th>
                        <th>평가</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rules.map((r) => {
                        // 발행 전용 규칙은 공통(draft) 검증에서는 평가하지 않는다
                        const applied = r.profile === "common" || d.mode === "publish";
                        return (
                          <tr key={r.iri} className={cx(!applied && "muted")}>
                            <td title={r.iri}>
                              <div className="bold">{r.name}</div>
                              <div className="mono tiny muted">{r.local}</div>
                            </td>
                            <td>
                              <SeverityBadge severity={r.severity} />
                            </td>
                            <td>{r.path ? <span className="kbd nowrap">{r.path}</span> : dash}</td>
                            <td>{r.message || dash}</td>
                            <td className="nowrap">{r.route ? `STEP ${r.route.step} · ${r.route.label}` : dash}</td>
                            <td className="nowrap">
                              {r.profile === "publish" ? <Badge tone="purple">발행 전용</Badge> : <Badge>공통</Badge>}
                              {!applied && <div className="tiny mt-4">이 모드에서는 평가 안 함</div>}
                            </td>
                            <td className="nowrap">{r.evaluator}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
            <Card title={`셰이프 원문 (Turtle) — ${SHAPE_MODES.find((m) => m.key === d.mode)?.label ?? d.mode}`}>
              {d.turtle ? <CodeBlock text={d.turtle} maxHeight={520} /> : <Empty>셰이프 원문이 없습니다</Empty>}
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}
