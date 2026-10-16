// 데이터 카탈로그 — 스튜디오 STEP 7 에서 발행한 정본의 목록(/catalog)과 상세(/catalog/:rid)
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, downloadFile, downloads } from "../api";
import { useAuth, useReference } from "../auth";
import type { CatalogEntry } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, ConfirmButton, Empty, KeyPill, QueryState, Tabs, cx, fmtDateTime, fmtNum, fmtPct, shortHash, useToast } from "../ui";

export function CatalogPage() {
  const { rid } = useParams();
  return rid ? <CatalogDetail key={rid} rid={rid} /> : <CatalogList />;
}

// ───────────── 공용 배지
function StatusBadge({ status }: { status: CatalogEntry["status"] }) {
  return status === "published" ? <Badge tone="ok">발행</Badge> : <Badge tone="err">철회</Badge>;
}

function KindBadge({ kind }: { kind: CatalogEntry["kind"] }) {
  return kind === "stream" ? <Badge tone="purple">스트림</Badge> : <Badge tone="info">데이터셋</Badge>;
}

function ReadinessBadge({ level }: { level: string | undefined }) {
  if (!level) return <span className="muted">—</span>;
  return <Badge tone={level === "ai-ready" ? "ok" : "warn"}>{level === "draft" ? "초안" : level}</Badge>;
}

function N2sfBadge({ grade }: { grade: string | null | undefined }) {
  if (!grade) return <span className="muted">—</span>;
  const tone = grade === "O" ? "ok" : grade === "C" ? "err" : grade === "S" ? "warn" : "muted";
  return (
    <Badge tone={tone} title="N²SF 보안등급">
      N²SF {grade}
    </Badge>
  );
}

const dash = <span className="muted">—</span>;

// ───────────── 목록
type KindFilter = "" | "dataset" | "stream";
type StatusFilter = "published" | "withdrawn";

const KIND_CHIPS: { key: KindFilter; label: string }[] = [
  { key: "", label: "전체" },
  { key: "dataset", label: "데이터셋" },
  { key: "stream", label: "스트림" },
];
const STATUS_CHIPS: { key: StatusFilter; label: string }[] = [
  { key: "published", label: "발행" },
  { key: "withdrawn", label: "철회" },
];

/** 선택한 패싯이 집계에서 빠졌어도(검색어를 바꾼 경우) 해제할 수 있게 칩으로 남긴다 */
function withSelected(rows: [string, number][], selected: string): [string, number][] {
  return selected && !rows.some(([label]) => label === selected) ? [[selected, 0], ...rows] : rows;
}

function CatalogList() {
  const [sp, setSp] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  // 필터는 주소에 둔다 — 상세에서 돌아오거나 주소를 공유해도 같은 목록이 보인다
  const q = sp.get("q") ?? "";
  const rawKind = sp.get("kind");
  const kind: KindFilter = rawKind === "dataset" || rawKind === "stream" ? rawKind : "";
  const status: StatusFilter = sp.get("status") === "withdrawn" ? "withdrawn" : "published";
  const theme = sp.get("theme") ?? "";
  const dataType = sp.get("data_type") ?? "";

  const patch = (changes: Record<string, string>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setSp(next, { replace: true });
  };

  // 검색어: 입력은 지역 상태로 받고 300ms 뒤(또는 Enter) 주소에 반영한다
  const [text, setText] = useState(q);
  const pushed = useRef(q);
  useEffect(() => {
    if (q !== pushed.current) {
      // 주소가 밖에서 바뀐 경우(헤더 메뉴 · 필터 초기화)만 입력란을 맞춘다
      pushed.current = q;
      setText(q);
    }
  }, [q]);
  const submit = (value: string) => {
    const v = value.trim();
    if (v === q) return;
    pushed.current = v;
    patch({ q: v });
  };
  // 타이머가 울릴 때는 그 사이 바뀐 다른 필터(주소)를 덮어쓰지 않도록 최신 submit 을 부른다
  const submitRef = useRef(submit);
  useEffect(() => {
    submitRef.current = submit;
  });
  useEffect(() => {
    const t = setTimeout(() => submitRef.current(text), 300);
    return () => clearTimeout(t);
  }, [text]);

  const params = { q, kind, theme, data_type: dataType, status };
  const list = useQuery({ queryKey: ["catalog", params], queryFn: () => api.catalog(params), placeholderData: keepPreviousData });

  const filtered = !!(q || kind || theme || dataType);
  const reset = () => {
    pushed.current = "";
    setText("");
    patch({ q: "", kind: "", theme: "", data_type: "" });
  };
  const open = (rid: string) => navigate(`/catalog/${encodeURIComponent(rid)}`, { state: { search: location.search } });
  const facets = list.data?.facets;

  return (
    <div>
      <h1 className="page-title">데이터 카탈로그</h1>
      <p className="page-sub">스튜디오에서 발행 모드 검증과 직렬화를 통과해 발행한 정본입니다. 식별자 · 제목 · 설명 · 제공기관 · 키워드 · 분류 · 조합 이름으로 찾습니다.</p>

      <div className="card tight">
        <div className="row wrap">
          <input
            className="input grow"
            style={{ minWidth: 220 }}
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(text)}
            placeholder="카탈로그 검색 — 여러 낱말은 모두 포함하는 항목만"
            aria-label="카탈로그 검색"
          />
          <div className="row gap-4">
            {KIND_CHIPS.map((k) => (
              <button key={k.key} className={cx("chip", kind === k.key && "on")} aria-pressed={kind === k.key} onClick={() => patch({ kind: k.key })}>
                {k.label}
              </button>
            ))}
          </div>
          <div className="row gap-4" role="group" aria-label="발행 상태">
            {STATUS_CHIPS.map((s) => (
              <button
                key={s.key}
                className={cx("chip", status === s.key && "on")}
                aria-pressed={status === s.key}
                onClick={() => patch({ status: s.key === "published" ? "" : s.key })}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        {facets && (
          <>
            <FacetRow label="주제영역" rows={withSelected(facets.theme, theme)} selected={theme} onToggle={(v) => patch({ theme: v === theme ? "" : v })} />
            <FacetRow label="데이터유형" rows={withSelected(facets.data_type, dataType)} selected={dataType} onToggle={(v) => patch({ data_type: v === dataType ? "" : v })} />
          </>
        )}
      </div>

      <QueryState q={list}>
        {list.data && (
          <>
            <div className="row between wrap mt-12 mb-8">
              <div className="row">
                <span>
                  <b>{fmtNum(list.data.total)}건</b> <span className="muted">· {status === "published" ? "발행 중인 항목" : "철회된 항목"}</span>
                </span>
                {list.isFetching && <span className="spinner" aria-label="불러오는 중" />}
              </div>
              {filtered && (
                <button className="link-btn small" onClick={reset}>
                  필터 초기화
                </button>
              )}
            </div>
            {list.data.items.length === 0 ? (
              <Empty>
                {filtered ? (
                  <>
                    조건에 맞는 항목이 없습니다 —{" "}
                    <button className="link-btn" onClick={reset}>
                      필터 초기화
                    </button>
                  </>
                ) : status === "withdrawn" ? (
                  "철회된 항목이 없습니다"
                ) : (
                  <>
                    발행된 항목이 없습니다 — <Link to="/studio">스튜디오</Link> STEP 7 에서 발행하면 여기에 등재됩니다
                  </>
                )}
              </Empty>
            ) : (
              <EntryTable items={list.data.items} onOpen={open} linkState={{ search: location.search }} />
            )}
          </>
        )}
      </QueryState>
    </div>
  );
}

function FacetRow(props: { label: string; rows: [string, number][]; selected: string; onToggle: (value: string) => void }) {
  if (props.rows.length === 0) return null;
  return (
    <div className="row wrap mt-8">
      <span className="label" style={{ width: 64 }}>
        {props.label}
      </span>
      {props.rows.map(([value, count]) => (
        <button key={value} className={cx("chip", props.selected === value && "on")} aria-pressed={props.selected === value} onClick={() => props.onToggle(value)}>
          {value}
          <span className="score">{fmtNum(count)}</span>
        </button>
      ))}
    </div>
  );
}

function EntryTable(props: { items: CatalogEntry[]; onOpen: (rid: string) => void; linkState: { search: string } }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>식별자</th>
            <th>제목 · 제공기관</th>
            <th>형태</th>
            <th>분류</th>
            <th>연계키</th>
            <th>이용조건</th>
            <th>준비도</th>
            <th>버전</th>
            <th>발행</th>
          </tr>
        </thead>
        <tbody>
          {props.items.map((e) => {
            const f = e.facets;
            const cls = f.classification || {};
            return (
              <tr key={e.resource_id} className="clickable" onClick={() => props.onOpen(e.resource_id)}>
                <td className="nowrap">
                  <Link className="mono bold" to={`/catalog/${encodeURIComponent(e.resource_id)}`} state={props.linkState} onClick={(ev) => ev.stopPropagation()}>
                    {e.resource_id}
                  </Link>
                  <div className="mt-4">
                    <KindBadge kind={e.kind} />
                    {e.status === "withdrawn" && (
                      <>
                        {" "}
                        <StatusBadge status={e.status} />
                      </>
                    )}
                  </div>
                </td>
                <td style={{ minWidth: 200 }}>
                  <div className="bold">{e.title}</div>
                  <div className="small dim">{e.publisher || "제공기관 미지정"}</div>
                  {e.description && (
                    <div className="small muted ellipsis" style={{ maxWidth: 320 }} title={e.description}>
                      {e.description}
                    </div>
                  )}
                </td>
                <td>
                  <div>{f.form || dash}</div>
                  {f.media_type && (
                    <div className="tiny muted mono ellipsis" style={{ maxWidth: 150 }} title={f.media_type}>
                      {f.media_type}
                    </div>
                  )}
                </td>
                <td>
                  <div className="row gap-4 wrap">
                    {(cls.theme || []).map((t) => (
                      <Badge key={`t-${t}`} tone="info" title="주제영역">
                        {t}
                      </Badge>
                    ))}
                    {(cls.dataType || []).map((t) => (
                      <Badge key={`d-${t}`} title="데이터유형">
                        {t}
                      </Badge>
                    ))}
                    {!cls.theme?.length && !cls.dataType?.length && dash}
                  </div>
                </td>
                <td>
                  <div className="row gap-4 wrap nowrap">{f.keys?.length ? f.keys.map((k) => <KeyPill key={`${k.key}-${k.table}-${k.column}`} code={k.key} label={k.label} />) : dash}</div>
                </td>
                <td>
                  <div>{f.license || dash}</div>
                  <div className="mt-4">
                    <N2sfBadge grade={f.n2sf} />
                  </div>
                </td>
                <td>
                  <ReadinessBadge level={f.readiness} />
                </td>
                <td className="nowrap mono">v{e.version}</td>
                <td className="nowrap">
                  <div>{fmtDateTime(e.published_at)}</div>
                  <div className="small muted">{e.published_by}</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ───────────── 상세
function CatalogDetail({ rid }: { rid: string }) {
  const location = useLocation();
  // 목록에서 넘어왔으면 그때의 필터로 돌아간다
  const state = location.state as { search?: string } | null;
  const back = `/catalog${state?.search ?? ""}`;
  const q = useQuery({ queryKey: ["catalog", "entry", rid], queryFn: () => api.catalogEntry(rid) });
  return (
    <div>
      <div className="mb-8">
        <Link to={back} className="bold">
          ← 목록
        </Link>
      </div>
      <QueryState q={q}>{q.data && <EntryView e={q.data} />}</QueryState>
    </div>
  );
}

function EntryView({ e }: { e: CatalogEntry }) {
  const { isAdmin } = useAuth();
  const { busy, toggle } = usePublishToggle(e);
  const f = e.facets;
  return (
    <div className="col gap-12">
      <div className="row between top wrap">
        <div>
          <h1 className="page-title">
            {e.title}
            <StatusBadge status={e.status} />
            <KindBadge kind={e.kind} />
            <Badge>v{e.version}</Badge>
          </h1>
          <div className="mono bold dim mt-4">{e.resource_id}</div>
        </div>
        {e.status === "published" && isAdmin && (
          <div className="col gap-4" style={{ alignItems: "flex-end", maxWidth: 400 }}>
            <ConfirmButton variant="danger" busy={busy} onConfirm={toggle} confirmLabel="한 번 더 눌러 철회">
              발행 철회
            </ConfirmButton>
            <span className="tiny muted right">철회해도 항목과 발행 ID 는 삭제되지 않습니다 (리니지 추적성 유지). 기본 목록에서만 빠지고 언제든 복원할 수 있습니다.</span>
          </div>
        )}
      </div>
      {e.status === "withdrawn" && (
        <Banner
          tone="warn"
          right={
            isAdmin ? (
              <Button variant="ok" busy={busy} onClick={toggle}>
                발행 복원
              </Button>
            ) : undefined
          }
        >
          <b>철회된 항목입니다.</b> 카탈로그 기본 목록에는 나오지 않지만 항목과 발행 ID 는 삭제되지 않고 그대로 남아, 이 항목을 가리키는 관계와 리니지를 계속 추적할 수 있습니다.
          {!isAdmin && " 복원은 관리자가 할 수 있습니다."}
        </Banner>
      )}

      <div className="grid c2">
        <Card title="기본 정보">
          <dl className="kv">
            <dt>IRI</dt>
            <dd className="mono">{e.iri}</dd>
            <dt>제공기관</dt>
            <dd>{e.publisher || dash}</dd>
            <dt>설명</dt>
            <dd>{e.description || dash}</dd>
            <dt>조합</dt>
            <dd>{e.collection_title || dash}</dd>
            <dt>프로세스</dt>
            <dd>{e.process_id != null ? <Link to={`/studio/${e.process_id}`}>{e.process_name || `프로세스 #${e.process_id}`}</Link> : e.process_name || dash}</dd>
            <dt>발행</dt>
            <dd>
              {e.published_by} · {fmtDateTime(e.published_at)}
            </dd>
            <dt>정본 체크섬</dt>
            <dd className="mono" title={e.checksum}>
              {shortHash(e.checksum, 16)}…
            </dd>
            <dt>트리플 수</dt>
            <dd>{fmtNum(f.triple_count)}</dd>
            <dt>준비도</dt>
            <dd>
              <ReadinessBadge level={f.readiness} />
            </dd>
            <dt>이용조건</dt>
            <dd>{f.license || dash}</dd>
            <dt>AI 활용 이용조건</dt>
            <dd>
              <AiTermsList terms={f.ai_terms} conditions={f.ai_conditions} />
            </dd>
            <dt>N²SF</dt>
            <dd>
              <N2sfBadge grade={f.n2sf} />
            </dd>
            <dt>형태 · 미디어타입</dt>
            <dd>
              {f.form || "—"}
              {f.media_type && <span className="mono muted"> · {f.media_type}</span>}
            </dd>
            <dt>배포본 ID</dt>
            <dd className="mono">{f.distribution_id || dash}</dd>
          </dl>
        </Card>
        <Card title="분류 · 연계">
          <ClassificationBlock e={e} />
        </Card>
      </div>

      <RelationsCard e={e} />
      <FormatsCard e={e} />
    </div>
  );
}

const CLASS_AXES: { key: keyof NonNullable<CatalogEntry["facets"]["classification"]>; label: string; tone: "info" | "muted" | "purple" }[] = [
  { key: "theme", label: "주제영역", tone: "info" },
  { key: "dataType", label: "데이터유형", tone: "muted" },
  { key: "granularity", label: "해상도", tone: "muted" },
  { key: "aiPurpose", label: "AI활용목적", tone: "purple" },
  { key: "governance", label: "거버넌스", tone: "muted" },
];

function ClassificationBlock({ e }: { e: CatalogEntry }) {
  const cls = e.facets.classification || {};
  const keys = e.facets.keys || [];
  const keywords = e.facets.keywords || [];
  return (
    <dl className="kv">
      {CLASS_AXES.map((axis) => {
        const values = cls[axis.key] || [];
        return (
          <Pair key={axis.key} label={axis.label}>
            {values.length ? (
              <div className="row gap-4 wrap">
                {values.map((v) => (
                  <Badge key={v} tone={axis.tone}>
                    {v}
                  </Badge>
                ))}
              </div>
            ) : (
              dash
            )}
          </Pair>
        );
      })}
      <Pair label="연계키">
        {keys.length ? (
          <div className="col gap-4">
            {keys.map((k) => (
              <div key={`${k.key}-${k.table}-${k.column}`} className="row gap-4 wrap nowrap">
                <KeyPill code={k.key} label={k.label} />
                {k.column && (
                  <span className="mono small dim">
                    {k.table ? `${k.table}.` : ""}
                    {k.column}
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          dash
        )}
      </Pair>
      <Pair label="키워드">
        {keywords.length ? (
          <div className="row gap-4 wrap">
            {keywords.map((k) => (
              <Badge key={k}>#{k}</Badge>
            ))}
          </div>
        ) : (
          dash
        )}
      </Pair>
    </dl>
  );
}

function Pair({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

/** 발행 정본의 관계 레코드. 조인 관계에는 서버가 컬럼 매핑·일치율·SSOT 순위를 함께 싣는다 (types.ts 에는 아직 없는 필드). */
type RelationFacet = NonNullable<CatalogEntry["facets"]["relations"]>[number] & {
  ssotPriority?: number;
  sourceColumn?: string;
  targetColumn?: string;
  matchRate?: number;
};

function RelationsCard({ e }: { e: CatalogEntry }) {
  const ref = useReference();
  const relations: RelationFacet[] = e.facets.relations || [];
  const hasDetail = relations.some((r) => r.sourceColumn || r.targetColumn || r.matchRate != null || r.ssotPriority != null);
  return (
    <Card title="관계" right={<span className="small muted">같은 조합 안에서 확정한 매핑 · 리니지</span>}>
      {relations.length === 0 ? (
        <Empty>이 항목에 기록된 관계가 없습니다</Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>유형</th>
                <th>대상</th>
                <th>연계키</th>
                <th>방향</th>
                {hasDetail && <th>조인 상세</th>}
              </tr>
            </thead>
            <tbody>
              {relations.map((r, i) => {
                const def = ref.relation_types.find((t) => t.type === r.type);
                const directed = def ? def.directed : true;
                return (
                  <tr key={`${r.type}-${r.target}-${r.direction}-${i}`}>
                    <td>
                      <Badge title={def?.desc}>{def?.label || r.type}</Badge>
                    </td>
                    <td className="bold">{r.target}</td>
                    <td>{r.key ? <KeyPill code={r.key} label={ref.key_labels[r.key]} /> : dash}</td>
                    <td className="nowrap">{!directed ? "↔ 방향 없음" : r.direction === "in" ? "← 대상에서 이 항목으로" : r.direction === "out" ? "→ 이 항목에서 대상으로" : dash}</td>
                    {hasDetail && (
                      <td>
                        <RelationDetail r={r} />
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function RelationDetail({ r }: { r: RelationFacet }) {
  const parts: ReactNode[] = [];
  if (r.sourceColumn || r.targetColumn) {
    parts.push(
      <span key="cols" className="mono">
        {r.sourceColumn || "?"} = {r.targetColumn || "?"}
      </span>,
    );
  }
  if (r.matchRate != null) parts.push(<span key="rate">일치율 {fmtPct(r.matchRate, 1)}</span>);
  if (r.ssotPriority != null) parts.push(<span key="ssot">SSOT {r.ssotPriority}순위</span>);
  if (parts.length === 0) return dash;
  return <div className="row wrap small">{parts}</div>;
}

// ───────────── 정본 · 파생 포맷
const FORMATS = [
  { key: "ttl", label: "Turtle", ext: "ttl" },
  { key: "jsonld", label: "JSON-LD", ext: "jsonld" },
  { key: "txt", label: "문장화", ext: "txt" },
  { key: "schema", label: "JSON 스키마", ext: "json" },
  { key: "croissant", label: "Croissant", ext: "croissant.json" },
  { key: "card", label: "데이터 카드", ext: "데이터카드.md" },
  { key: "dict", label: "데이터 사전", ext: "데이터사전.csv" },
] as const;
type Fmt = (typeof FORMATS)[number]["key"];

function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text; // 파싱되지 않으면 서버가 준 그대로 보여 준다
  }
}

function contentOf(e: CatalogEntry, fmt: Fmt): string {
  switch (fmt) {
    case "ttl":
      return e.turtle || "";
    case "jsonld":
      return e.jsonld || "";
    case "txt":
      return e.text_summary || "";
    case "schema":
      return e.schema_json ? prettyJson(e.schema_json) : "";
    default:
      return e.documents?.[fmt] ?? "";
  }
}

function FormatsCard({ e }: { e: CatalogEntry }) {
  const ref = useReference();
  const toast = useToast();
  const [fmt, setFmt] = useState<Fmt>("ttl");
  const [busy, setBusy] = useState<Fmt | null>(null);
  const text = contentOf(e, fmt);
  const def = ref.formats.find((x) => x.key === fmt);

  const download = async (key: Fmt, ext: string) => {
    setBusy(key);
    try {
      await downloadFile(downloads.catalogRaw(e.resource_id, key), `${e.resource_id}${ext.includes(".") ? "_" : "."}${ext}`);
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card
      title="정본 · 파생 포맷"
      right={
        <div className="row gap-4 wrap">
          <span className="small muted">내려받기</span>
          {FORMATS.map((x) => (
            <Button
              key={x.key}
              size="sm"
              busy={busy === x.key}
              disabled={!contentOf(e, x.key)}
              title={contentOf(e, x.key) ? `${e.resource_id}.${x.ext}` : "발행 시 이 포맷을 만들지 않았습니다"}
              onClick={() => download(x.key, x.ext)}
            >
              ⤓ {x.label}
            </Button>
          ))}
        </div>
      }
    >
      <Tabs tabs={FORMATS.map((x) => ({ key: x.key, label: x.label }))} value={fmt} onChange={setFmt} />
      {def && (
        <p className="small muted mb-8">
          {def.label} · <span className="mono">{def.media_type}</span> — {def.use}
        </p>
      )}
      {text ? <CodeBlock text={text} wrap={fmt === "txt" || fmt === "card" || fmt === "dict"} light={fmt === "txt" || fmt === "card" || fmt === "dict"} /> : <Empty>이 항목에는 {FORMATS.find((x) => x.key === fmt)?.label} 포맷이 없습니다 — 발행할 때 변환 대상에서 빠졌습니다</Empty>}
    </Card>
  );
}

// ───────────── 발행 철회 · 복원 (관리자)
/** 철회는 항목을 지우지 않고 상태만 바꾼다. 두 동작 모두 서버가 활동 로그에 남긴다. */
function usePublishToggle(e: CatalogEntry) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    const withdraw = e.status === "published";
    setBusy(true);
    try {
      if (withdraw) await api.withdraw(e.resource_id);
      else await api.republish(e.resource_id);
      await qc.invalidateQueries({ queryKey: ["catalog"] }); // 목록과 이 상세 모두
      void qc.invalidateQueries({ queryKey: ["activities"] });
      toast.ok(`${withdraw ? "발행 철회" : "발행 복원"} — ${e.resource_id}`);
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };
  return { busy, toggle };
}

// AI 활용 이용조건 (가이드라인 3.4.5 표 39) — 이름은 서버 canonical.AI_TERMS 와 같다
const AI_TERM_LABELS: [string, string][] = [
  ["ai_training", "AI 학습"],
  ["ai_combination", "결합"],
  ["ai_automated_access", "자동화 접근"],
  ["ai_bulk_access", "대량 호출"],
  ["ai_redistribution", "재배포"],
];
const AI_STATUS: Record<string, { label: string; tone: "ok" | "warn" | "err" }> = {
  permitted: { label: "허용", tone: "ok" },
  conditional: { label: "조건부", tone: "warn" },
  prohibited: { label: "불허", tone: "err" },
};

function AiTermsList({ terms, conditions }: { terms?: Record<string, string>; conditions?: string | null }) {
  const t = terms || {};
  return (
    <div className="col gap-4">
      <div className="row wrap" style={{ gap: 4 }}>
        {AI_TERM_LABELS.map(([k, label]) => {
          const st = AI_STATUS[t[k]];
          return (
            <Badge key={k} tone={st?.tone || "muted"}>
              {label} {st?.label || "미정"}
            </Badge>
          );
        })}
      </div>
      {conditions && <span className="small">{conditions}</span>}
    </div>
  );
}
