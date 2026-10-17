// API 응답 타입. 근거: docs/api-samples/*.json (백엔드 serializers.py)

export type Role = "admin" | "worker" | "viewer";

export interface User {
  id: number;
  username: string;
  name: string;
  role: Role;
  org_label: string | null;
  email: string | null;
  active: boolean;
  created_at: string;
}

export interface Org {
  id: number;
  code: string;
  label: string;
  kind: string;
  note: string | null;
  active: boolean;
  iri: string;
}

export interface TaxCode {
  id: number;
  code: string;
  label: string;
  definition: string | null;
  active: boolean;
  extra: Record<string, unknown>;
  iri: string;
}

export interface TaxAxis {
  code: string; // F1..F6 | K | N2SF
  name: string;
  nature: "필수" | "권장" | "보조";
  multi: boolean;
  version: string | null;
  rdf_property: string | null;
  description: string | null;
  scheme_iri: string;
  codes: TaxCode[];
}

export interface FixRoute {
  key: string | null;
  step: number;
  label: string;
  focus: string | null;
}

export interface MetaField {
  name: string;
  property: string;
  label: string;
  level: "필수" | "권장" | "선택";
  type: "text" | "textarea" | "org" | "media_type" | "url" | "duration" | "late_policy" | "tags" | "periodicity" | "date" | "ai_term";
  scope: "all" | "dataset" | "stream";
  approval?: boolean;
  /** 가이드라인 근거 위치 (예: "표 9 데이터명"). 가이드라인에 없는 제품 필드는 비어 있다 */
  guide?: string;
  /** "card": 부록 4 데이터 카드에만 있는 항목, "ai": AI 활용 이용조건(3.4.5 표 39) — 둘 다 데이터 카드 탭에서 입력 */
  group?: "card" | "ai";
  card_item?: string;
  /** 항목의 뜻 (화면 도움말) */
  help?: string;
}

// ───────────── STEP 3 데이터 사전 · 데이터 카드
export interface DictRow {
  table: string;
  column: string;
  type: string;
  type_label: string;
  description: string;
  unit: string;
  codes: string;
  required: boolean | null;
  null_rate: number | null;
  distinct: number | null;
  missing_markers: string[];
  samples: string[];
  pii: string | null;
  key: string | null;
  /** 컬럼 민감 항목: 담당자가 표시한 개인정보 유형 (none · pseudonymized · personal · sensitive) */
  personal_data: string | null;
  /** 자동 후보 (표시하지 않은 컬럼에만) */
  personal_suggested: string | null;
  personal_suggested_why: string | null;
  deid: { method: string; note: string | null; by?: string; at?: string } | null;
}

export interface DictPayload {
  dataset_id: number;
  rows: DictRow[];
  described: number;
  total: number;
  sensitive: { marked: number; deid: number; suggested_count: number; needs_deid: string[]; dataset_personal_data: string | null; dataset_personal_label: string | null };
  options: { personal_data: Record<string, string>; deid_methods: Record<string, string> };
}

export interface CardItem {
  item: string;
  content: string;
  source: "자동" | "입력" | "작성 필요" | "해당 시";
  optional: boolean;
  filled: boolean;
  note?: string;
}

export interface CardPreview {
  dataset_id: number;
  sections: { section: string; items: CardItem[] }[];
  filled: number;
  total: number;
}

export interface FormatDef {
  key: "ttl" | "jsonld" | "txt" | "schema" | "croissant" | "card" | "dict";
  label: string;
  tag: string;
  suffix: string;
  media_type: string;
  use: string;
}

export interface Reference {
  steps: { n: number; label: string; owner: string }[];
  fix_routes: Record<string, { step: number; label: string; focus: string | null }>;
  media_types: { value: string; ext: string; form: string }[];
  late_policies: string[];
  accrual_periodicities: { value: string; label: string }[];
  extra_classes: { iri: string; desc: string; form: string }[];
  relation_types: { type: RelationType; label: string; desc: string; directed: boolean; needs_key: boolean }[];
  roles: { value: Role; label: string; desc: string }[];
  meta_fields: MetaField[];
  formats: FormatDef[];
  base_iri: string;
  def_ns: string;
  shapes_version: string;
  max_upload_mb: number;
  upload_exts: string[];
  key_labels: Record<string, string>;
}

// ───────────── 원천(Asset) · 프로파일
export interface KeyCandidate {
  code: string; // K1..K9
  label: string;
  table: string;
  column: string;
  score: number; // 0~1
  reason: string;
  distinct?: number;
  sampled?: boolean;
}

export interface ColumnProfile {
  name: string;
  type: "string" | "integer" | "number" | "datetime" | "boolean";
  count: number;
  missing: number;
  null_rate: number;
  distinct: number;
  unique: boolean;
  samples: string[];
  max_len: number;
  missing_markers: { marker: string; count: number }[];
  min?: number | string;
  max?: number | string;
  date_formats?: { format: string; count: number }[];
  iso8601?: boolean;
  interval?: { seconds: number; label: string | null; duration: string | null };
  pii?: { kind: string; basis: string };
}

export interface TableProfile {
  name: string;
  rows: number;
  truncated: boolean;
  header_row: number;
  preamble: string[];
  columns: ColumnProfile[];
  sample_rows: string[][];
}

export interface Profile {
  status: "ok" | "error" | "empty" | "unsupported" | "stream";
  tables: TableProfile[];
  warnings: string[];
  error?: string;
}

export interface Asset {
  id: number;
  name: string;
  kind: "dataset" | "stream";
  source: "upload" | "stream";
  filename: string | null;
  ext: string | null;
  size: number | null;
  size_label: string | null;
  sha256: string | null;
  media_type: string | null;
  data_form: string | null;
  description: string | null;
  org: Org | null;
  stream: {
    temporal_resolution?: string | null;
    event_time_column?: string | null;
    endpoint_url?: string | null;
    timezone?: string | null;
    fields?: { name: string; type: string }[];
  };
  profile_status: Profile["status"] | null;
  profile_summary: string;
  table_count: number;
  column_count: number;
  row_count: number;
  warnings: string[];
  error: string | null;
  key_candidates: KeyCandidate[];
  keys: string[];
  created_at: string;
  profile?: Profile; // 상세 조회에서만
  minted_id?: string | null;
  used_in?: { id: number; name: string; status: string }[];
}

// ───────────── 프로세스 · 데이터셋
export interface Process {
  id: number;
  name: string;
  status: "active" | "completed" | "trashed";
  current_step: number;
  combo_title: string | null;
  combo_description: string | null;
  combo_source: "manual" | "suggestion" | null;
  combo_confirmed_at: string | null;
  pub_mode: boolean;
  lineage_waiver_reason: string | null;
  lineage_waived_at: string | null;
  /** 조합 등급 (3.6.1 결합 후 재검토): floor = 구성 최고 등급, explicit = 담당자가 직접 정함 */
  combo_grading?: { floor: string | null; floor_label: string | null; grade: string | null; grade_label: string | null; explicit: boolean; below_floor: boolean; reason: string | null; unset: string[]; mixed: boolean };
  dataset_count: number;
  selected_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  trashed_at: string | null;
  steps_done?: number[];
  dataset_names?: string[];
}

export interface Readiness {
  required: string[];
  missing: string[];
  recommended_missing: string[];
  level: "ai-ready" | "draft";
}

export interface KeyBinding {
  code: string;
  table?: string | null;
  column?: string | null;
}

export interface Classification {
  F1?: string[];
  F2?: string[];
  F3?: string[];
  F4?: string[];
  F5?: string[];
  F6?: string[];
  K?: KeyBinding[];
  N2SF?: string;
  /** 등급 판단 근거 (가이드라인 3.6.1 판단 항목) */
  N2SF_BASIS?: GradeBasis;
  /** 표 41 공유 불가 유형: 수동 지정과 자동 신호 해제 사유 */
  SHARE_PROHIBITED?: { manual?: string[]; overrides?: Record<string, string>; by?: string; at?: string };
  /** 메타데이터 공개 수준: detail · listing · internal */
  META_VISIBILITY?: MetaVisibility;
}
export type MetaVisibility = "detail" | "listing" | "internal";
export interface GradeBasis {
  personal_data?: string;
  reidentification?: string;
  legal?: string;
  legal_refs?: string;
  reason?: string;
  suggested?: string | null;
  by?: string;
  at?: string;
}
/** 서버가 계산한 등급 상태 (dataset.grading) */
export interface GradingState {
  grade: string | null;
  grade_label: string | null;
  suggested: string | null;
  suggested_label: string | null;
  reasons: string[];
  basis: GradeBasis;
  basis_complete: boolean;
  below_suggested: boolean;
  below_reason: string | null;
  /** 기관 등급표에서 이 자산에 매칭된 가장 높은 등급 */
  org_grade: { grade: string; label: string | null; name: string; system: string | null; entries: number; legal_basis: string | null; personal_data: string | null } | null;
  org_conflict: boolean;
  /** 데이터 사전 컬럼 민감 항목 요약 */
  columns: { marked: number; deid: number; suggested_count: number; needs_deid: string[]; dataset_personal_data: string | null; dataset_personal_label: string | null };
  prohibited: { types: string[]; labels: string[]; auto: Record<string, string>; overrides: Record<string, string>; manual: string[]; blocked: boolean; mode: "block" | "review" };
  visibility: MetaVisibility;
  visibility_explicit: boolean;
  options: {
    personal_data: Record<string, string>;
    reidentification: Record<string, string>;
    legal: Record<string, string>;
    prohibited_types: Record<string, string>;
    visibilities: Record<string, string>;
    min_reason: number;
  };
}

export interface Dataset {
  id: number;
  process_id: number;
  asset: Asset;
  selected: boolean;
  in_combo: boolean;
  position: number;
  title: string;
  kind: "dataset" | "stream";
  meta: Record<string, any>; // META 필드 값 + _auto: 자동 제안된 필드명 목록
  approved_fields: string[];
  approval_fields: string[];
  extra_classes: string[];
  meta_confirmed_at: string | null;
  classification: Classification;
  grading?: GradingState;
  class_confirmed_at: string | null;
  resource_id: string;
  minted: boolean;
  minted_id: string | null;
  draft_id: string;
  authoring_activity: string | null;
  // 조합 구성원에만 있음
  readiness?: Readiness;
  checksum?: string;
  triple_count?: number;
  iri?: string;
  warnings?: string[];
}

export interface Gate {
  step: number;
  done: boolean;
  /** 들어가서 볼 수 있는지 (7·8 은 지난 결과가 있으면 열람 가능) */
  can_enter: boolean;
  reason: string;
  /** 새로 실행할 수 있는지 (열람보다 엄격: 상류 결과가 최신이어야 함) */
  can_run: boolean;
  run_reason: string;
  progress?: string;
}
export interface RerunResult {
  validation: { run_id: number; pass_count: number; total: number; mode: string } | null;
  serialization: { run_id: number; ok_count: number; fail_count: number } | null;
  diagnosis: { run_id: number; score: number; max_score: number } | null;
  stopped: string | null;
  state: ProcessState;
}

export interface ProcessState {
  gates: Gate[];
  combo_ok: boolean;
  lineage_resolved: boolean;
  validation: { run_id: number | null; stale: string | null; done: boolean; mode: "draft" | "publish" | null; pass_count: number; total: number };
  serialization: { run_id: number | null; stale: string | null; done: boolean; ok_count: number };
  diagnosis: { run_id: number | null; stale: string | null; done: boolean; score: number | null; max_score: number | null };
}

export interface ProcessDetail {
  process: Process;
  datasets: Dataset[];
  state: ProcessState;
  removed_from_combo?: string[];
}

export interface Activity {
  id: number;
  code: string;
  type: string;
  text: string;
  agent_type: "person" | "software";
  actor: string;
  process_id: number | null;
  dataset_id: number | null;
  at: string;
  iri: string;
}

// ───────────── STEP 1·2 추천
export interface ComboSuggestion {
  asset_ids: number[];
  dataset_ids: number[];
  names: string[];
  shared_keys: { code: string; label: string }[];
  score: number;
  confidence: number;
  reasons: string[];
  method: string;
}

export interface ComboWarning {
  level: "error" | "warn";
  dataset_id: number;
  name: string;
  code: string;
  message: string;
}

// ───────────── STEP 3 미리보기
export type Severity = "Violation" | "Warning" | "Info";

export interface ValidationRow {
  source: "gate0" | "shacl";
  severity: Severity;
  shape: string;
  shape_iri: string | null;
  message: string;
  focus: string | null;
  focus_iri: string | null;
  path: string | null;
  value: string | null;
  route: FixRoute | null;
}

export interface Gate0Check {
  key: "parse" | "prefix" | "utf8" | "mint" | "identity";
  name: string;
  ok: boolean;
  detail: string;
  skipped?: boolean;
  route?: string | null;
}

export interface Preview {
  resource_id: string;
  iri: string;
  checksum: string;
  triple_count: number;
  readiness: Readiness;
  turtle: string;
  jsonld: string;
  text: string;
  record: Record<string, any>;
  validation: { passed: boolean; violation_count: number; warning_count: number; info_count: number; results: ValidationRow[]; gate0: Gate0Check[] };
}

// ───────────── STEP 4 분류 추천
export interface ClassSuggestion {
  axis: string;
  code: string;
  score: number; // 0~100
  reason: string;
  table?: string;
  column?: string;
}

// ───────────── STEP 5 관계
export type RelationType = "JOINED_ON" | "GROUPED_WITH" | "DERIVED_FROM";

export interface JoinStats {
  computed?: boolean;
  reason?: string;
  source_distinct?: number;
  target_distinct?: number;
  matched?: number;
  source_match_rate?: number;
  target_match_rate?: number;
  unmatched_samples?: string[];
  sampled?: boolean;
}

export interface Relation {
  id: number;
  type: RelationType;
  status: "draft" | "confirmed";
  priority: number;
  source_id: number;
  source_name: string;
  target_id: number;
  target_name: string;
  key_code: string | null;
  key_label: string | null;
  source_table: string | null;
  source_column: string | null;
  target_table: string | null;
  target_column: string | null;
  note: string | null;
  stats: JoinStats;
  iri: string;
  created_at: string;
  confirmed_at: string | null;
}

export interface RelationCandidate {
  source_id: number;
  source_name: string;
  target_id: number;
  target_name: string;
  key_code: string;
  key_label: string;
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
  score: number;
  stats: JoinStats | null;
  already: boolean;
}

export interface RelationsPayload {
  relations: Relation[];
  candidates: RelationCandidate[];
  lineage_resolved: boolean;
  waiver: { reason: string; at: string } | null;
  types: Reference["relation_types"];
}

export type NodeType = "Collection" | "Dataset" | "Service" | "Agent" | "Activity" | "Distribution" | "Table" | "Column" | "JoinKey";

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  sub: string;
  dataset_id?: number;
  detail?: Record<string, string>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
  status?: "draft" | "confirmed";
  relation_id?: number;
  priority?: number;
  detail?: Record<string, string>;
}

export interface GraphData {
  level: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_counts: Record<string, number>;
  edge_counts: Record<string, number>;
}

// ───────────── STEP 6 검증
export interface ValidationDataset {
  dataset_id: number;
  name: string;
  resource_id: string;
  checksum: string;
  gate0: Gate0Check[];
  conforms: boolean;
  passed: boolean;
  violation_count: number;
  warning_count: number;
  info_count: number;
  results: ValidationRow[];
  triple_count: number;
}

export interface ValidationRun {
  id: number;
  process_id: number;
  mode: "draft" | "publish";
  shapes_version: string;
  status: string;
  pass_count: number;
  fail_count: number;
  warning_count: number;
  started_at: string;
  ended_at: string | null;
  activity: string | null;
  datasets: ValidationDataset[];
}

export interface ValidationLatest {
  run: ValidationRun | null;
  stale: string | null;
  lineage_resolved: boolean;
  mint: { dataset_id: number; name: string; minted_id: string | null; draft_id: string }[];
}

export interface ShapeRule {
  iri: string;
  name: string;
  local: string;
  message: string;
  path: string | null;
  severity: Severity;
  route: FixRoute | null;
  profile: "common" | "publish";
  evaluator: string;
}

// ───────────── STEP 7 직렬화
export interface Artifact {
  id: number;
  dataset_id: number;
  dataset_name: string;
  fmt: FormatDef["key"];
  filename: string;
  media_type: string;
  size: number;
  size_label: string;
  sha256: string;
  set_checksum: string;
}

export interface ArtifactContent {
  id: number;
  filename: string;
  fmt: FormatDef["key"];
  media_type: string;
  content: string;
  sha256: string;
  set_checksum: string;
  size: number;
}

export interface SelfVerify {
  dataset_id: number;
  name: string;
  resource_id: string;
  checksum: string;
  readiness: string;
  triple_count: number;
  passed: boolean;
  checks: { name: string; ok: boolean; detail: string }[];
}

export interface SerializationRun {
  id: number;
  process_id: number;
  validation_run_id: number;
  mode: "draft" | "publish";
  formats: string[];
  ok_count: number;
  fail_count: number;
  self_verify: SelfVerify[];
  started_at: string;
  ended_at: string | null;
  activity: string | null;
  artifacts: Artifact[];
}

export interface SerializationLatest {
  run: SerializationRun | null;
  stale: string | null;
  formats: FormatDef[];
  publish_blocked: string[]; // 비어 있으면 발행 가능
}

// ───────────── STEP 8 진단
export type DiagStatus = "met" | "partial" | "unmet" | "pending" | "na";

export type DiagMethod = "AUTO-GRAPH" | "AUTO-PROFILE" | "AUTO-DERIVED" | "HUMAN-ATTEST";

export interface DiagItem {
  id: string;
  area: string;
  /** 짧은 항목명 (메타데이터는 원문 항목명, 체크리스트는 화면용 요약) */
  name: string;
  method: DiagMethod;
  /** 근거 위치 (예: "표 9 데이터 관리 메타데이터", "부록 3 공통 · 형식 및 구조") */
  basis: string;
  // 아래 6개는 규칙 세트 fde-rules-1.0 부터 온다 (그 전 실행 결과에는 없다)
  /** 가이드라인 원문 문구 */
  text?: string | null;
  /** 필수 · 권장 · 선택 · 원칙 */
  level?: string | null;
  /** 메타데이터 속성 (가이드라인 표기, 예: dct:title) */
  property?: string | null;
  /** 이 스튜디오가 정한 판정 기준 */
  criteria?: string | null;
  /** 종합 항목이 참조하는 연결 항목 */
  related?: { id: string; name: string; status: DiagStatus }[];
  /** 담당자 확인으로 판정을 기록할 수 있는 항목인지 */
  attestable?: boolean;
  allow_na?: boolean;
  remedy: string | null;
  difficulty: number;
  datasets: { id: number; name: string; status: DiagStatus; detail: string; focus?: string }[];
  evidence: string[];
  route: FixRoute | null;
  /** outdated: 확인한 뒤에 조합 구성이 바뀌어 판정에 반영되지 않은 기록 */
  attestation: { status: DiagStatus; note: string | null; evidence: string | null; by: string; at: string; outdated?: boolean } | null;
  status: DiagStatus;
  score: number | null;
}

export interface DiagArea {
  id: string;
  name: string;
  guideline_items: number;
  implemented: number;
  items: number;
  score: number;
  pct: number | null;
  auto: number;
  manual: number;
}

export interface DiagRun {
  id: number;
  process_id: number;
  ruleset_version: string;
  score: number;
  max_score: number;
  pct: number;
  summary: {
    areas: DiagArea[];
    methods: { id: string; name: string; items: number; total?: number; met: number; partial: number; unmet: number; pending: number }[];
    roadmap: {
      rank: number;
      item_id: string;
      action: string;
      name: string;
      gain: number;
      difficulty: "낮음" | "중간" | "높음";
      basis: string;
      level?: string | null;
      method?: DiagMethod;
      route: FixRoute | null;
    }[];
    dataset_count: number;
    mode: "draft" | "publish";
    guideline: string;
    guideline_total: number;
    implemented_total: number;
    scored_total: number;
    note: string;
    validation_run_id: number | null;
    validation_stale: string | null;
    counts: Record<DiagStatus, number>;
    potential_score: number;
  };
  items: DiagItem[];
  started_at: string;
  ended_at: string | null;
  activity: string | null;
}

export interface DiagLatest {
  run: DiagRun | null;
  stale: string | null;
  /** 현재 저장된 담당자 확인 (항목 ID → 확인 내용) */
  attestations: Record<string, { status: DiagStatus; note: string | null; evidence: string | null; by: string; at: string }>;
  /** 최근 진단 이후에 기록되어 아직 점수에 반영되지 않은 항목 ID */
  pending_attestations: string[];
  ruleset: {
    version: string;
    guideline: string;
    note: string;
    guideline_total: number;
    implemented_total: number;
    methods: { id: string; name: string }[];
    areas: { id: string; name: string; guideline_items: number }[];
    /** 판정 방식별 항목 수 */
    method_counts: Record<string, number>;
  };
}

// ───────────── 카탈로그 · 대시보드 · 관리
export interface CatalogEntry {
  resource_id: string;
  iri: string;
  kind: "dataset" | "stream";
  title: string;
  description: string | null;
  publisher: string | null;
  process_id: number | null;
  process_name: string | null;
  collection_title: string | null;
  version: number;
  status: "published" | "withdrawn";
  checksum: string;
  facets: {
    classification?: { theme?: string[]; dataType?: string[]; granularity?: string[]; aiPurpose?: string[]; governance?: string[] };
    license?: string | null;
    n2sf?: string | null;
    meta_visibility?: MetaVisibility;
    grade_basis?: { personal_data?: string; reidentification?: string; legal?: string; suggested?: string | null } | null;
    share_prohibited?: string[];
    /** AI 활용 이용조건 (3.4.5 표 39): 항목 이름 → permitted | conditional | prohibited. 없는 항목은 미정 */
    ai_terms?: Record<string, string>;
    ai_conditions?: string | null;
    /** AI 초안을 채택해 담당자가 확정한 칸 이름들 (FDE_AI_ASSIST_NOTICE 가 켜져 있을 때만) */
    ai_assisted?: string[];
    /** AI 기본법 제34조 학습용데이터 개요 대응 작성률 "n/8" */
    ai_act_overview?: string | null;
    keys?: { key: string; label: string; column?: string; table?: string }[];
    keywords?: string[];
    media_type?: string | null;
    form?: string | null;
    triple_count?: number;
    readiness?: string;
    relations?: { type: string; target: string; direction?: string; key?: string; ssotPriority?: number; sourceColumn?: string; targetColumn?: string; matchRate?: number }[];
    distribution_id?: string | null;
  };
  published_by: string;
  published_at: string;
  turtle?: string;
  jsonld?: string;
  text_summary?: string | null;
  schema_json?: string | null;
  /** 같은 정본에서 만든 문서 산출물 (상세 조회에만 있음): croissant · card · dict */
  documents?: Partial<Record<"croissant" | "card" | "dict", string>>;
}

export interface CatalogList {
  total: number;
  items: CatalogEntry[];
  facets: { theme: [string, number][]; data_type: [string, number][] };
}

export interface Dashboard {
  counts: {
    assets: number;
    streams: number;
    processes_active: number;
    processes_completed: number;
    catalog_published: number;
    minted: number;
    activities: number;
  };
  recent_processes: (Process & { steps_done: number[]; validation: ProcessState["validation"] })[];
  recent_activities: Activity[];
  now: string;
}

export interface MintRegistry {
  records: { id: number; kind: string; minted_id: string; iri: string; asset_id: number; asset_name: string | null; process_id: number | null; minted_at: string; note: string | null }[];
  next: { DST: string; SVC: string };
  policy: { draft_pattern: string; published_pattern: string; distribution_pattern: string; activity_pattern: string; rule: string; iri_base: string };
}

// ───────────── AI 에이전트(MCP)
export type AgentKeyState = "active" | "expired" | "revoked";
export interface AgentKey {
  id: number;
  name: string;
  purpose: string | null;
  prefix: string;
  grades: string[];
  tools: string[];
  daily_limit: number;
  state: AgentKeyState;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  stats_30d: { ok: number; denied: number; error: number };
  key?: string; // 발급 응답에만 있다
}
export interface AgentCall {
  id: number;
  key_id: number | null;
  key_label: string;
  tool: string;
  arguments: Record<string, unknown>;
  resource_ids: string[];
  status: "ok" | "denied" | "error";
  message: string | null;
  duration_ms: number;
  at: string;
}
export interface McpInfo {
  path: string;
  transport: string;
  tools: { name: string; description: string }[];
  grades: string[];
}

// ───────────── 발행 검수 큐 (표 40 HITL)
export type RiskLevel = "high" | "medium" | "low";
export interface ReviewSignal {
  code: string;
  severity: RiskLevel;
  label: string;
  detail: string;
  datasets: string[];
}
export interface ReviewDataset {
  dataset_id: number;
  resource_id: string;
  title: string | null;
  checksum: string;
  kind: string;
  n2sf: string | null;
  pii: string[];
  ai_terms: Record<string, string>;
  current_version: number | null;
  change: "new" | "update" | "same";
}
export interface ReviewAssessment {
  level: RiskLevel;
  level_label: string;
  signals: ReviewSignal[];
  datasets: ReviewDataset[];
  diagnosis: { run_id: number; score: number; max_score: number; ratio: number; stale: string | null } | null;
  pii_checked: boolean;
}
export interface ReviewRequest {
  /** 상세 조회에만 있음: note(본인 승인 가능, 사유 필수) | deny(본인 승인 금지) */
  self_approve_policy?: "note" | "deny";
  id: number;
  process_id: number;
  process_name: string | null;
  status: "pending" | "approved" | "rejected" | "withdrawn";
  status_label: string;
  message: string | null;
  risk_level: RiskLevel;
  risk_label: string;
  signals: ReviewSignal[];
  datasets: ReviewDataset[];
  diagnosis: ReviewAssessment["diagnosis"];
  requested_by: string;
  requested_by_id: number | null;
  requested_at: string;
  reviewer: string | null;
  decided_at: string | null;
  decision_note: string | null;
  acknowledged: string[];
  self_approved: boolean;
  published: string[];
  serialization_run_id: number | null;
  /** 검수 대기 중일 때만: 요청 뒤에 발행 대상이 바뀐 사유 (없으면 null) */
  stale?: string | null;
}
export interface PublishReview {
  blocked: string[];
  assessment: ReviewAssessment | null;
  pending: ReviewRequest | null;
  latest: ReviewRequest | null;
  direct_publish: boolean;
  direct_publish_reason: string | null;
}

// ───────────── AI 초안 제안
export interface AiStatus {
  enabled: boolean;
  model: string | null;
  fields: string[];
  rule_fields: string[];
  note: string;
  /** dataset_id 를 주었을 때: 이 데이터셋에 쓸 수 없는 사유 (C 등급 · 담당자 제외) */
  blocked_reason?: string | null;
  grade?: string | null;
  excluded?: { by: string; at: string; reason: string | null } | null;
}
export interface AiDraft {
  text: string | string[];
  basis: string;
  source: "llm" | "rule";
}
export interface AiDraftResult {
  drafts: Record<string, AiDraft>;
  model: string | null;
  usage: { input_tokens: number; output_tokens: number; model: string } | null;
  pii_withheld?: number;
}

// ───────────── STEP 7 AI 활용 시뮬레이션
export interface SimSource {
  dataset?: string;
  property: string;
  value: string;
}
export interface SimTrace {
  tool: string;
  arguments: Record<string, unknown>;
  status: "ok" | "denied" | "error";
  resource_ids: string[];
  duration_ms: number;
  preview: string;
}
export interface SimulationRun {
  id: number;
  process_id: number;
  scenario: "chat" | "agent";
  scenario_label: string;
  with_metadata: boolean;
  dataset_ids: number[];
  question: string;
  result: {
    answer: string;
    answered?: boolean;
    sources?: SimSource[];
    missing?: string[];
    context_parts?: Record<string, string[]>;
    trace?: SimTrace[];
    tool_calls?: number;
    turns?: number;
    tools_available?: string[];
  };
  usage: { input_tokens: number; output_tokens: number; model?: string };
  model: string;
  duration_ms: number;
  group_id: string | null;
  created_by: string;
  created_at: string;
}
export interface SimulationStatus {
  enabled: boolean;
  model: string | null;
  scenarios: { key: "chat" | "agent"; label: string; desc: string; examples: string[] }[];
  datasets: { id: number; title: string; has_artifacts: boolean; blocked_reason: string | null }[];
  published_count: number;
  note: string;
  runs: SimulationRun[];
}

// ───────────── 즉시 진단 (STEP 3·4 미리보기)
export interface DiagPreviewItem {
  id: string;
  name: string;
  area: string;
  method: DiagMethod;
  level?: string | null;
  status: DiagStatus;
  previous: DiagStatus | null;
  changed: boolean;
  provisional: boolean;
  route: FixRoute | null;
  detail: string | null;
  focus: string | null;
  dataset_status: DiagStatus | null;
}
export interface DiagPreview {
  items: DiagPreviewItem[];
  counts: Record<DiagStatus, number>;
  score: number;
  max_score: number;
  last_run: { id: number; score: number; max_score: number; at: string } | null;
  improved: DiagPreviewItem[];
  regressed: DiagPreviewItem[];
  provisional_note: string | null;
  dataset_id: number | null;
}

export interface OrgGradeEntry {
  id: number;
  kind: string;
  name: string;
  system: string | null;
  department: string | null;
  grade: string;
  grade_label: string | null;
  personal_data: string | null;
  legal_basis: string | null;
  note: string | null;
  asset_id: number | null;
  match_score: number;
  source_file: string | null;
  imported_at: string;
  candidates: { asset_id: number; name: string; filename: string | null; score: number }[];
}
