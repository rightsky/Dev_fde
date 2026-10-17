// ARD 관리 › 발행본 상세 — 외부에 내준 정본 1건 (포맷 미리보기 · 내려받기 · 제출 패키지 · 철회/복원)
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, downloadFile, downloads } from "../api";
import { useAuth, useReference } from "../auth";
import type { CatalogEntry } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, ConfirmButton, Empty, QueryState, Tabs, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";

export function ArdPublishedPage() {
  const { rid = "" } = useParams();
  const q = useQuery({ queryKey: ["catalog", "entry", rid], queryFn: () => api.catalogEntry(rid) });
  return (
    <div>
      <div className="mb-8">
        <Link to="/ard?tab=published" className="bold">
          ← 발행본 목록
        </Link>
      </div>
      <QueryState q={q}>{q.data && <EntryView e={q.data} />}</QueryState>
    </div>
  );
}

function PackageButton({ datasetId, title }: { datasetId: number; title: string }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      size="sm"
      variant="primary"
      busy={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await downloadFile(downloads.ardPackage(datasetId), `${title}_제출패키지.zip`);
          void qc.invalidateQueries({ queryKey: ["ard"] });
        } catch (e) {
          toast.error(e);
        } finally {
          setBusy(false);
        }
      }}
    >
      ⤓ 제출 패키지 (ZIP)
    </Button>
  );
}

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
  const tone = grade === "O" ? "ok" : grade === "C" ? "err" : grade === "S" || grade === "S1" || grade === "S2" ? "warn" : "muted";
  return (
    <Badge tone={tone} title="N²SF 보안등급">
      N²SF {grade}
    </Badge>
  );
}

const dash = <span className="muted">—</span>;

function EntryView({ e }: { e: CatalogEntry }) {
  const { isAdmin } = useAuth();
  const { busy, toggle } = usePublishToggle(e);
  const f = e.facets;
  return (
    <div className="col gap-12">
      <div className="row between top wrap">
        <div>
          <h1 className="page-title row wrap" style={{ gap: 8, alignItems: "center" }}>
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
              {f.meta_visibility && f.meta_visibility !== "detail" && (
                <Badge tone={f.meta_visibility === "internal" ? "err" : "warn"} title="메타데이터 공개 수준">{f.meta_visibility === "internal" ? "내부 한정" : "목록만 공개"}</Badge>
              )}
              {f.grade_basis && (
                <div className="small muted mt-4" title="등급 판단 근거 (가이드라인 3.6.1)">
                  근거: {[f.grade_basis.personal_data, f.grade_basis.reidentification, f.grade_basis.legal].filter(Boolean).join(" · ")}
                  {f.grade_basis.suggested && ` (제안 ${f.grade_basis.suggested})`}
                </div>
              )}
              {f.share_prohibited && f.share_prohibited.length > 0 && <div className="small t-err mt-4">표 41 공유 불가 유형 {f.share_prohibited.length}건</div>}
            </dd>
            {(f.ai_assisted?.length || f.ai_act_overview) && (
              <>
                <dt>AI 기본법</dt>
                <dd>
                  {f.ai_act_overview && (
                    <span title="제34조제1항제2호 학습용데이터 개요로 인용할 수 있는 설명 요소의 작성 현황 (참고). 데이터 카드 '부가' 절에 항목별 근거가 있습니다">
                      학습용데이터 개요 {f.ai_act_overview}
                    </span>
                  )}
                  {f.ai_assisted && f.ai_assisted.length > 0 && (
                    <div className="small muted" title="생성형 AI 초안을 담당자가 검토·확정한 칸 (제31조제2항 취지의 표시). 정본 그래프에 fde:aiAssisted 이력으로 남습니다">
                      AI 보조 작성 · 담당자 확정: {f.ai_assisted.join(" · ")}
                    </div>
                  )}
                </dd>
              </>
            )}
            <dt>형태 · 미디어타입</dt>
            <dd>
              {f.form || "—"}
              {f.media_type && <span className="mono muted"> · {f.media_type}</span>}
            </dd>
            <dt>배포본 ID</dt>
            <dd className="mono">{f.distribution_id || dash}</dd>
          </dl>
        </Card>
        <Card title="배포">
          <dl className="kv">
            <dt>MCP 노출</dt>
            <dd>
              {e.status === "published" && f.meta_visibility !== "internal" && !f.ai_excluded && f.n2sf !== "C" ? <Badge tone="info">노출 (키 등급 범위 안)</Badge> : <Badge tone="muted">비노출</Badge>}
              {f.ai_excluded && <div className="tiny muted">담당자가 외부 AI 전송 제외로 표시</div>}
            </dd>
            <dt>제출 패키지</dt>
            <dd>
              {e.dataset_id != null ? (
                <PackageButton datasetId={e.dataset_id} title={e.title} />
              ) : (
                <span className="muted">프로세스가 없어 만들 수 없습니다</span>
              )}
              <div className="tiny muted mt-4">JSON-LD · Croissant · 데이터 카드 · 데이터 사전 + manifest.json (체크섬 · 발행 ID · 등급). 포털 · 수요처 제출용.</div>
            </dd>
            <dt>분류</dt>
            <dd className="small">
              {Object.entries(f.classification || {}).flatMap(([k, v]) => (v || []).map((x) => `${k}:${x}`)).join(" · ") || dash}
            </dd>
            <dt>연계</dt>
            <dd className="small">{f.relations && f.relations.length > 0 ? f.relations.map((r) => `${r.type} → ${r.target}`).join(" · ") : dash}</dd>
          </dl>
        </Card>
      </div>

      <FormatsCard e={e} />
    </div>
  );
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
