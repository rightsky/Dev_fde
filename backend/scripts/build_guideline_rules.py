"""가이드라인 v1.1 원문(md)에서 80항목의 문구를 그대로 뽑아 guideline_rules.json 을 만든다.

사용: python -I scripts/build_guideline_rules.py <가이드라인.md> app/data/guideline_rules.json
원문 문구(text)는 md 표에서 읽는다. 표 9 는 md 변환본에 빠져 있어 PDF 29~30쪽을 보고 옮겼다.
판정 방식(method·resolver·criteria·remedy)은 이 스튜디오의 설계이며 원문에 있는 내용이 아니다.
"""
import json
import re
import sys

md_path, out_path = sys.argv[1], sys.argv[2]
lines = open(md_path, encoding="utf-8").read().splitlines()


def cells(line):
    line = line.strip()
    line = line[1:] if line.startswith("|") else line
    line = line[:-1] if line.endswith("|") else line
    return [c.strip() for c in line.split("|")]


def unescape(t):
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!~|>])", r"\1", t).strip()


def section(start_pat, end_pat):
    i = next(n for n, l in enumerate(lines) if re.search(start_pat, l))
    j = next(n for n in range(i + 1, len(lines)) if re.search(end_pat, lines[n]))
    return lines[i:j]


# ---------- 15개 원칙
principles = {}
for l in section(r"^## 공공데이터의 인공지능 친화적 관리 FAIR 원칙", r"^## CHAPTER 01"):
    m = re.match(r"^\|원칙 (\d\d)\|(.+)\|$", l)
    if m:
        principles[int(m.group(1))] = unescape(m.group(2))
assert len(principles) == 15, len(principles)

# ---------- 표 10~12
def meta_table(title_pat):
    rows = []
    sec = section(title_pat, r"^> \\\*\\\*예시")
    for l in sec:
        if l.startswith("|") and not l.startswith("|-") and not l.startswith("|구분|항목명"):
            c = cells(l)
            rows.append({"name": unescape(c[1]), "property": unescape(c[2]), "level": c[3], "text": unescape(c[4])})
    return rows


t10 = meta_table(r"\[표 10\] 데이터 계보 메타데이터")
t11 = meta_table(r"\[표 11\] 데이터 이용 메타데이터")
t12 = meta_table(r"\[표 12\] 데이터 품질 메타데이터")
assert (len(t10), len(t11), len(t12)) == (4, 2, 4)

# ---------- 표 9 (PDF 29~30쪽에서 옮김)
t9 = [
    ("데이터명", "dct:title", "필수", "데이터셋의 공식 명칭"),
    ("데이터 설명", "dct:description", "필수", "데이터셋의 내용, 보유 목적, 수집 대상 등 설명"),
    ("관련법령", "dct:references", "필수", "법령 참조, 법적 근거"),
    ("소관기관 (운영부서명)", "dct:creator", "필수", "데이터셋을 생산·관리하는 주체"),
    ("제공기관", "dct:publisher", "필수", "데이터셋을 대외적으로 배포·게재하는 기관"),
    ("제공시스템", "dcat:landingPage", "필수", "배포 또는 추가 정보에 대한 액세스를 제공하는 웹 페이지"),
    ("갱신주기", "dct:accrualPeriodicity", "필수", "데이터셋 업데이트 빈도"),
    ("업무/주제분류체계", "dcat:theme", "필수", "데이터셋의 카테고리를 참조. 데이터셋은 여러 테마와 연결 가능"),
    ("키워드", "dcat:keyword", "필수", "검색 및 분류를 위한 핵심 키워드"),
    ("고유식별자", "dct:identifier", "필수", "중복되지 않는 영구 식별자"),
    ("담당자연락처", "dcat:contactPoint", "필수", "데이터셋 담당자에 대한 연락처 정보. 이름, 전화번호, 이메일을 하위로 제공"),
    ("언어", "dct:language", "필수", "데이터셋의 언어를 참조하며 여러 언어가 있는 경우 이 속성을 반복 가능"),
    ("배포본", "dcat:distribution", "필수", "데이터셋에 배포본이 존재함을 의미"),
    ("접속 URL", "dcat:accessURL", "필수", "데이터셋의 배포본 URL"),
    ("데이터용량", "dcat:byteSize", "필수", "데이터의 크기(바이트)"),
    ("데이터셋 유형", "dcat:mediaType", "필수", "수치, 이미지, 음성, 영상 등 구분"),
    ("시간범위", "dct:temporal", "권장", "데이터셋에서 다루는 시간적 기간"),
    ("공간범위", "dct:spatial", "권장", "데이터셋에서 다루는 지리적 영역"),
    ("연계데이터셋", "dct:relation", "선택", "연계 데이터셋이나 참조 리소스"),
]
t9 = [{"name": a, "property": b, "level": c, "text": d} for a, b, c, d in t9]

# ---------- 부록3 체크리스트
common = []
group = None
for l in section(r"^### 공통 — 공공데이터셋 점검 항목", r"^### 유형별"):
    if l.startswith("|") and not l.startswith("|-") and not l.startswith("|분류|"):
        c = cells(l)
        group = c[0] or group
        common.append({"group": group, "level": c[1], "text": unescape(c[2])})
assert len(common) == 33, len(common)
typed = []
group = None
for l in section(r"^### 유형별 — 데이터 특성에 따른 추가 점검 항목", r"^## 부록4"):
    if l.startswith("|") and not l.startswith("|-") and not l.startswith("|데이터 유형|"):
        c = cells(l)
        group = c[0] or group
        typed.append({"group": group, "level": c[1], "text": unescape(c[2])})
assert len(typed) == 5, len(typed)
req = [c for c in common if c["level"] == "필수"]
rec = [c for c in common if c["level"] == "권장"]
assert (len(req), len(rec)) == (15, 18)
# 이 스튜디오는 표 형식 파일과 스트림만 다루므로 이미지/영상 2항목은 진단 대상에서 뺀다
typed = [t for t in typed if t["group"] != "이미지 / 영상"]
assert len(typed) == 3


def ask(q, partial=None):
    r = {"resolver": {"type": "ask", "query": "ASK { " + q + " }"}}
    if partial:
        r["partial"] = {"query": "ASK { " + partial + " }"}
    return r


def builtin(name):
    return {"resolver": {"type": "builtin", "name": name}}


def derived(*ids):
    return {"resolver": {"type": "derived", "from": list(ids)}, "method": "AUTO-DERIVED"}


ATTEST = {"resolver": {"type": "attest"}, "method": "HUMAN-ATTEST", "allow_na": True}
G = "AUTO-GRAPH"
PR = "AUTO-PROFILE"
H = "HUMAN-ATTEST"


def meta3(focus, **kw):
    return {"route": "meta3", "focus": focus, **kw}


# ---------- 판정 설계 (id → 설정)
spec = {
    # A1 메타데이터 필수 (표 9 ~ 11)
    "M-01": {**ask("?this dcterms:title ?v"), "method": G, "route": "title", "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:title 이 있으면 충족", "remedy": "STEP 3 에서 데이터명을 입력한다"},
    "M-02": {**ask("?this dcterms:description ?v"), "method": G, **meta3("description"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:description 이 있으면 충족",
             "remedy": "STEP 3 에서 데이터 설명(내용·보유 목적·수집 대상)을 입력한다"},
    "M-03": {**ask("?this dcterms:references ?v"), "method": G, **meta3("references"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:references 가 있으면 충족",
             "remedy": "STEP 3 의 관련법령에 근거 법령 이름이나 법령 URL 을 입력한다"},
    "M-04": {**ask("?this dcterms:creator ?v"), "method": G, **meta3("creator"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:creator 가 있으면 충족",
             "remedy": "STEP 3 의 소관기관에 데이터를 생산·관리하는 부서 이름을 입력한다"},
    "M-05": {**ask("?this dcterms:publisher ?v"), "method": G, "route": "publisher", "difficulty": 1,
             "criteria": "승인된 제공기관이 dcterms:publisher 로 정본 그래프에 있으면 충족 (승인 전에는 미입력으로 본다)",
             "remedy": "STEP 3 에서 제공기관을 고르고 승인한다"},
    "M-06": {**ask("?this dcat:landingPage ?v"), "method": G, **meta3("landing_page"), "difficulty": 1,
             "criteria": "정본 그래프에 dcat:landingPage 가 있으면 충족",
             "remedy": "STEP 3 의 제공시스템에 데이터를 안내·제공하는 웹 페이지 주소를 입력한다"},
    "M-07": {**builtin("periodicity"), "method": G, **meta3("accrual_periodicity"), "focus_stream": "temporal_resolution", "difficulty": 1,
             "criteria": "dcterms:accrualPeriodicity 가 표준 표기(ISO 8601 duration 또는 irregular)이면 충족, 비표준 표기면 부분. 스트림은 승인된 dcat:temporalResolution 으로 판정",
             "remedy": "STEP 3 에서 갱신주기를 선택한다 (스트림은 시간 해상도를 승인한다)"},
    "M-08": {**ask("?this dcat:theme ?v"), "method": G, "route": "class4", "focus": "F1", "difficulty": 1,
             "criteria": "정본 그래프에 dcat:theme 이 있으면 충족 (STEP 4 의 F1 주제영역)",
             "remedy": "STEP 4 에서 F1 주제영역을 1개 이상 선택한다"},
    "M-09": {**ask("?this dcat:keyword ?v"), "method": G, **meta3("keywords"), "difficulty": 1,
             "criteria": "정본 그래프에 dcat:keyword 가 1개 이상 있으면 충족", "remedy": "STEP 3 에서 키워드를 입력한다"},
    "M-10": {**builtin("minted"), "method": G, "route": "mint", "difficulty": 1,
             "criteria": "민팅 대장에 발행 ID(DST-000001 형식)가 등록되어 있으면 충족. 초안 ID 만 있으면 영구 식별자가 아니므로 미흡",
             "remedy": "STEP 6 에서 관리자가 발행 ID 를 발급한다"},
    "M-11": {**ask("?this dcat:contactPoint ?c . ?c vcard:fn ?n . { ?c vcard:hasEmail ?e } UNION { ?c vcard:hasTelephone ?t }",
                   "?this dcat:contactPoint ?c"), "method": G, **meta3("contact_name"), "difficulty": 1,
             "criteria": "dcat:contactPoint 에 이름과 이메일(또는 전화번호)이 함께 있으면 충족, 일부만 있으면 부분",
             "remedy": "STEP 3 에서 담당 부서·담당자와 담당 이메일(또는 전화번호)을 입력한다"},
    "M-12": {**ask("?this dcterms:language ?v"), "method": G, **meta3("language"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:language 가 있으면 충족", "remedy": "STEP 3 에서 언어 코드를 입력한다 (예: ko)"},
    "M-13": {**ask("?this dcat:distribution ?d"), "method": G, "route": "mediaType", "applies": "dataset", "difficulty": 1,
             "criteria": "정본 그래프에 dcat:distribution 이 있으면 충족. 배포본은 데이터셋 유형(미디어타입)을 승인하면 만들어진다. 스트림은 해당 없음",
             "remedy": "STEP 3 에서 데이터셋 유형(미디어타입)을 승인한다"},
    "M-14": {**ask("{ ?this dcat:distribution ?d . ?d dcat:accessURL ?u } UNION { ?this dcat:endpointURL ?u }"), "method": G,
             **meta3("access_url"), "focus_stream": "endpoint_url", "difficulty": 1,
             "criteria": "배포본에 dcat:accessURL 이 있으면 충족. 스트림은 dcat:endpointURL 로 판정",
             "remedy": "STEP 3 에서 데이터셋 유형을 승인한 뒤 접속 URL 을 입력한다 (스트림은 엔드포인트 URL)"},
    "M-15": {**ask("?this dcat:distribution ?d . ?d dcat:byteSize ?b"), "method": G, "route": "mediaType", "applies": "dataset", "difficulty": 1,
             "criteria": "배포본에 dcat:byteSize 가 있으면 충족. 업로드한 파일 크기를 배포본에 자동으로 적는다. 스트림은 해당 없음",
             "remedy": "STEP 3 에서 데이터셋 유형(미디어타입)을 승인하면 파일 크기가 배포본에 기록된다"},
    "M-16": {**ask("?this dcat:distribution ?d . ?d dcat:mediaType ?m"), "method": G, "route": "mediaType", "applies": "dataset", "difficulty": 1,
             "criteria": "배포본에 dcat:mediaType 이 있으면 충족. 스트림은 해당 없음",
             "remedy": "STEP 3 에서 데이터셋 유형(미디어타입)을 고르고 승인한다"},
    "M-17": {**ask("?this owl:versionInfo ?v"), "method": G, **meta3("version"), "difficulty": 1,
             "criteria": "정본 그래프에 owl:versionInfo 가 있으면 충족", "remedy": "STEP 3 에서 버전을 입력한다 (예: 2025.01.v1)"},
    "M-18": {**ask("?this dcterms:issued ?v"), "method": G, **meta3("issued"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:issued 가 있으면 충족", "remedy": "STEP 3 에서 등록일시(최초 등록일)를 입력한다"},
    "M-19": {**ask("?this dcterms:modified ?v"), "method": G, **meta3("modified"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:modified 가 있으면 충족", "remedy": "STEP 3 에서 수정일시(마지막 수정일)를 입력한다"},
    "M-20": {**ask("?this adms:versionNotes ?v"), "method": G, **meta3("version_notes"), "difficulty": 1,
             "criteria": "정본 그래프에 adms:versionNotes 가 있으면 충족",
             "remedy": "STEP 3 의 버전 노트에 이전 버전과 달라진 점을 적는다 (첫 공개라면 '최초 공개')"},
    "M-21": {**ask("?this dcterms:license ?v", "?this dcterms:accessRights ?v"), "method": G, "route": "license", "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:license 가 있으면 충족 (STEP 4 의 F4 에서 공공누리 유형 지정). 제공 조건(dcterms:accessRights)만 있으면 부분",
             "remedy": "STEP 4 의 F4 유통·이용조건에서 공공누리 유형을 지정한다"},
    "M-22": {**ask("?this dcterms:rights ?v"), "method": G, **meta3("rights"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:rights 가 있으면 충족",
             "remedy": "STEP 3 의 저작권에 저작자 표시, 영리 이용, 변경 허용 여부를 적는다"},
    # A2 메타데이터 권장·선택 (표 9 · 12)
    "O-01": {**ask("?this dcterms:temporal ?v"), "method": G, **meta3("temporal_start"), "applies": "dataset", "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:temporal 이 있으면 충족. 스트림은 해당 없음",
             "remedy": "STEP 3 에서 시간범위 시작·종료를 입력한다"},
    "O-02": {**ask("?this dcterms:spatial ?v"), "method": G, **meta3("spatial"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:spatial 이 있으면 충족", "remedy": "STEP 3 에서 공간범위를 입력한다"},
    "O-03": {**builtin("related"), "method": G, "route": "lineage5", "difficulty": 2,
             "criteria": "조합 안의 다른 데이터셋과 확정된 관계가 있어 dcterms:relation 이 정본 그래프에 있으면 충족. 조합에 데이터셋이 1건뿐이면 해당 없음",
             "remedy": "STEP 5 에서 조합 안의 다른 데이터셋과의 관계를 확정한다"},
    "O-04": {**ask("?this rai:dataBiases ?v"), "method": G, **meta3("rai_data_biases"), "difficulty": 1,
             "criteria": "정본 그래프에 rai:dataBiases 가 있으면 충족", "remedy": "STEP 3 의 데이터 편향성에 확인된 편향 유형을 적는다"},
    "O-05": {**ask("?this dqv:hasQualityAnnotation ?v"), "method": G, **meta3("quality_annotation"), "difficulty": 1,
             "criteria": "정본 그래프에 dqv:hasQualityAnnotation 이 있으면 충족",
             "remedy": "STEP 3 의 품질 검증 정보에 수행한 품질 검토·평가 내용을 적는다"},
    "O-06": {**ask("?this rai:knownLimitations ?v"), "method": G, **meta3("rai_known_limitations"), "difficulty": 1,
             "criteria": "정본 그래프에 rai:knownLimitations 가 있으면 충족",
             "remedy": "STEP 3 의 데이터 한계에 제한사항과 해석할 때 유의할 점을 적는다"},
    "O-07": {**ask("?this rai:dataCollectionMissingData ?v"), "method": G, **meta3("rai_missing_data"), "difficulty": 1,
             "criteria": "정본 그래프에 rai:dataCollectionMissingData 가 있으면 충족",
             "remedy": "STEP 3 의 결측치 정보에 결측 비율과 처리 방식을 적는다"},
    # A3 15개 원칙 — 연결 항목은 이 스튜디오가 정한 대응이며 가이드라인이 정한 것이 아니다
    "P-01": {**derived("C-01", "C-02", "C-03"), "section": "2.1.1"},
    "P-02": {**derived("R-13", "R-16"), "section": "2.1.2"},
    "P-03": {**derived("C-04", "C-05"), "section": "2.2.1"},
    "P-04": {**derived("C-06", "R-10", "O-04", "O-06", "M-20"), "section": "2.2.2"},
    "P-05": {**derived("C-09", "C-10", "R-05"), "section": "2.3"},
    "P-06": {**derived("C-07", "C-08", "R-03", "R-04"), "section": "2.4"},
    "P-07": {**derived("R-06", "R-17", "M-18", "M-19"), "section": "3.1"},
    "P-08": {**derived("C-14", "M-04", "M-11"), "section": "3.2"},
    "P-09": {**derived("M-06", "M-14", "R-08"), "section": "3.3"},
    "P-10": {**builtin("mcp_hint"), "method": H, "allow_na": True, "section": "3.4", "difficulty": 2,
             "criteria": "발행본이 AI 에이전트(MCP)에게 열려 있으면 접근 키·호출 이력을 자동 증빙으로 붙이고 담당자가 확인한다. "
                         "에이전트 키로 접근할 수 없는 데이터면 해당 없음",
             "remedy": "관리 › AI 에이전트(MCP)에서 접근 등급·도구를 정해 키를 발급하고, 호출 이력과 보안 위험 검토 결과(3.4절 표 39·표 40)를 확인해 증빙을 남긴다"},
    "P-11": {**derived("C-15"), "section": "3.5"},
    "P-12": {**ask("?this fde:n2sfGrade ?g . ?this fde:governanceMode ?m",
                   "{ ?this fde:n2sfGrade ?g } UNION { ?this fde:governanceMode ?m }"),
             "method": G, "section": "3.6", "route": "class4", "focus": "N2SF", "difficulty": 1,
             "criteria": "보안등급(N²SF)과 F6 거버넌스(공유 범위)가 둘 다 지정되어 있으면 충족, 하나만 있으면 부분",
             "remedy": "STEP 4 에서 N²SF 보안등급과 F6 거버넌스를 지정한다"},
    "P-13": {**derived("M-04", "M-05", "R-06"), "section": "3.7"},
    "P-14": {**derived("C-12", "C-13", "M-03", "R-18"), "section": "3.8"},
    "P-15": {**ask("?this dcat:theme ?t . ?this fde:joinKey ?k . ?k fde:keyConcept ?c", "{ ?this dcat:theme ?t } UNION { ?this fde:joinKey ?k }"),
             "method": G, "section": "3.9", "route": "class4", "difficulty": 1,
             "criteria": "주제 분류(dcat:theme)와 연계키(K) 배정이 둘 다 있으면 충족, 하나만 있으면 부분",
             "remedy": "STEP 4 에서 F1 주제영역을 고르고 연계키(K)를 배정한다"},
    # A4 체크리스트 공통 필수
    "C-01": {**builtin("open_format"), "method": PR, "name": "개방형 표준 포맷 제공", "step": 1, "applies": "dataset", "difficulty": 3,
             "criteria": "원천 파일 형식이 가이드라인 2.1.1 의 권장 오픈 포맷(CSV·JSON·XML·Parquet 등. 탭 구분 텍스트 TSV 도 같은 부류로 본다)이면 충족, 비권장 포맷(XLS·XLSX·HWP 등)이면 미흡, 두 목록에 없는 형식이면 부분. 스트림은 해당 없음",
             "remedy": "CSV·JSON·Parquet 같은 개방형 포맷으로 변환한 파일을 STEP 1 에서 원천으로 등록한다"},
    "C-02": {**builtin("structured"), "method": PR, "name": "기계 처리가 가능한 구조화", "step": 1, "difficulty": 3,
             "criteria": "프로파일러가 표와 컬럼을 읽어 냈고 헤더 위에 제목 줄 같은 군더더기가 없으면 충족. 읽기는 했지만 헤더 앞 줄이 있거나 이름 없는 컬럼이 있으면 부분, 표로 읽지 못하면 미흡",
             "remedy": "첫 줄이 컬럼 이름이고 한 줄이 한 건인 표 형태로 파일을 정리해 다시 등록한다"},
    "C-03": {**builtin("schema_defined"), "method": G, "name": "데이터 구조(스키마) 정의", **meta3("extra_classes"), "difficulty": 1,
             "criteria": "컬럼 이름·자료형·필수 여부가 CSVW 스키마로 정본 그래프에 있으면 충족. 스트림은 등록한 스키마 필드가 있으면 충족",
             "remedy": "STEP 3 의 추가 클래스에서 csvw:Table 을 선택한다. 프로파일한 컬럼 구조가 스키마로 정본에 들어간다"},
    "C-04": {**builtin("machine_readable"), "method": G, "name": "표준 스키마 메타데이터 제공", "step": 7, "difficulty": 1,
             "criteria": "STEP 7 에서 DCAT 메타데이터를 Turtle 과 JSON-LD 로 산출했고 자가검증을 통과했으면 충족. JSON-LD 가 없으면 부분",
             "remedy": "STEP 6 검증을 통과시킨 뒤 STEP 7 에서 변환을 실행한다"},
    "C-05": {**derived(*[f"M-{n:02d}" for n in range(1, 23)]), "name": "메타데이터 필수 항목 누락 없음"},
    "C-06": {**builtin("data_dictionary"), "method": G, "name": "데이터 사전 제공", **meta3("dictionary"), "difficulty": 1,
             "criteria": "STEP 7 에서 데이터 사전을 산출했고 모든 컬럼에 정의가 적혀 있으면 충족, 절반 이상이면 부분, 그 미만이거나 산출하지 않았으면 미흡. 컬럼 이름·자료형·결측률은 자동으로 들어가고 정의·단위·코드값은 사람이 적는다",
             "remedy": "STEP 3 의 데이터 사전 탭에서 컬럼마다 정의·단위·코드값 의미를 적은 뒤 STEP 6 검증과 STEP 7 변환을 다시 실행한다"},
    "C-07": {**builtin("iso8601"), "method": PR, "name": "날짜·시간·코드 표기 형식 일관", "step": 1, "applies": "dataset", "difficulty": 3,
             "criteria": "날짜·시각 컬럼이 전부 ISO 8601 형식이면 충족, 일부만 맞으면 부분. 날짜·시각 컬럼이 없으면 해당 없음. 코드값 표기는 자동으로 보지 않는다",
             "remedy": "원천의 날짜·시각 값을 YYYY-MM-DD 또는 YYYY-MM-DDThh:mm:ss 형식으로 바꿔 다시 등록한다"},
    "C-08": {**ATTEST, "name": "동일 개념에 동일 용어 사용", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다",
             "remedy": "같은 개념을 가리키는 컬럼 이름·코드값·라벨이 데이터셋 사이에서 같은지 점검하고 결과를 증빙으로 남긴다"},
    "C-09": {**builtin("missing_markers"), "method": PR, "name": "결측값·특수값 표기 통일", "step": 1, "applies": "dataset", "difficulty": 3,
             "criteria": "프로파일에서 찾은 결측 표기가 1종 이하면 충족, 2종 이상 섞여 있으면 미흡",
             "remedy": "원천의 결측 표기를 한 가지(빈 값 또는 NULL)로 통일해 다시 등록한다"},
    "C-10": {**ask("?this dqv:hasQualityAnnotation ?v"), "method": G, "name": "품질평가 수행 여부와 결과 명시", **meta3("quality_annotation"), "difficulty": 1,
             "criteria": "정본 그래프에 dqv:hasQualityAnnotation 이 있으면 충족",
             "remedy": "STEP 3 의 품질 검증 정보에 품질평가를 했는지와 그 결과를 적는다"},
    "C-11": {**ATTEST, "name": "합성 데이터·자동 주석 구분 표기", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다. 합성 데이터나 자동 주석이 없으면 해당 없음으로 기록한다",
             "remedy": "합성 데이터나 기계가 단 주석이 들어 있는지 확인하고, 있다면 어디에 어떻게 표기했는지 증빙으로 남긴다"},
    "C-12": {**builtin("pii"), "method": H, "allow_na": True, "name": "개인정보 보호조치 적용", "difficulty": 2,
             "criteria": "컬럼 이름과 값 패턴으로 개인정보 의심 컬럼을 찾는다. 찾지 못하면 해당 없음, 찾으면 담당자가 보호조치를 증빙과 함께 확인한다",
             "remedy": "의심 컬럼에 적용한 비식별·가명처리 조치를 확인하고 증빙을 남긴다"},
    "C-13": {**ask("?this dcterms:license ?v", "?this dcterms:accessRights ?v"), "method": G, "name": "라이선스 표시와 메타데이터 제공", "route": "license", "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:license 가 있으면 충족. 제공 조건(dcterms:accessRights)만 있으면 부분",
             "remedy": "STEP 4 의 F4 유통·이용조건에서 공공누리 유형을 지정한다"},
    "C-14": {**ask("?this dcat:contactPoint ?c . ?c vcard:fn ?n . { ?c vcard:hasEmail ?e } UNION { ?c vcard:hasTelephone ?t } . { ?this dcterms:creator ?o } UNION { ?this dcterms:publisher ?o }",
                   "{ ?this dcat:contactPoint ?c } UNION { ?this dcterms:creator ?o } UNION { ?this dcterms:publisher ?o }"),
             "method": G, "name": "책임 주체와 연락 창구 명시", **meta3("contact_name"), "difficulty": 1,
             "criteria": "책임 기관(소관기관 또는 제공기관)과 담당 연락처(이름 + 이메일 또는 전화)가 메타데이터에 모두 있으면 충족, 일부만 있으면 부분. 창구를 실제로 운영하는지는 자동으로 보지 않는다",
             "remedy": "STEP 3 에서 소관기관, 담당 부서·담당자, 담당 이메일을 입력한다"},
    "C-15": {**ATTEST, "name": "오류 신고·피드백 체계 운영", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다",
             "remedy": "오류 신고와 개선 요청을 받는 창구, 처리 절차를 확인하고 그 위치를 증빙으로 남긴다"},
    # A5 체크리스트 공통 권장
    "R-01": {**builtin("schema_hint"), "method": H, "allow_na": True, "name": "데이터 검증 기준 제공", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다. 자료형과 필수 여부는 CSVW 스키마로 자동 산출되지만 허용값·관계 제약은 문서로 확인해야 한다",
             "remedy": "허용값·필수값·형식·관계 제약을 적은 검증 기준 문서의 제공 위치를 증빙으로 남긴다"},
    "R-02": {**builtin("large_format"), "method": PR, "name": "대용량 데이터의 압축·적합 포맷 제공", "step": 1, "applies": "dataset", "difficulty": 3,
             "criteria": "원천 파일이 100MB 이상일 때만 본다(이 스튜디오의 기준). Parquet 이면 충족, 아니면 미흡. 100MB 미만이면 해당 없음",
             "remedy": "대용량 파일은 Parquet 으로 변환하거나 압축해 제공한다"},
    "R-03": {**ask("?this dcterms:conformsTo ?v"), "method": G, "name": "적용 표준과 기준 문서화", **meta3("conforms_to"), "difficulty": 1,
             "criteria": "정본 그래프에 dcterms:conformsTo 가 있으면 충족",
             "remedy": "STEP 3 의 준수 표준에 적용한 표준을 적는다 (예: ISO 8601, 행정표준코드, EPSG:5186)"},
    "R-04": {**ATTEST, "name": "도메인 표준 용어체계와의 정합성 점검", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다. 해당 도메인에 표준 용어체계나 온톨로지가 없으면 해당 없음으로 기록한다",
             "remedy": "도메인 표준 용어체계와의 매핑·검증 절차를 확인하고 증빙을 남긴다"},
    "R-05": {**ask("?this rai:dataCollectionMissingData ?v"), "method": G, "name": "결측값·특수값의 정의와 처리 원칙 제공", **meta3("rai_missing_data"), "difficulty": 1,
             "criteria": "정본 그래프에 rai:dataCollectionMissingData 가 있으면 충족",
             "remedy": "STEP 3 의 결측치 정보에 결측값의 정의, 발생 사유, 처리 원칙을 적는다"},
    "R-06": {**builtin("provenance"), "method": G, "name": "원천·수집경로·가공 이력 제공", **meta3("provenance"), "difficulty": 1,
             "criteria": "출처·가공 이력(dcterms:provenance)이 적혀 있거나 다른 데이터셋에서 파생된 관계(prov:wasDerivedFrom)가 확정되어 있으면 충족. 카탈로그 작성 이력(prov:wasGeneratedBy)만 있으면 부분",
             "remedy": "STEP 3 의 출처·가공 이력에 원천 시스템, 수집 방식, 정제·비식별 처리 내용을 적는다 (다른 데이터셋에서 만든 데이터라면 STEP 5 에서 파생 관계를 확정한다)"},
    "R-07": {**ATTEST, "name": "정제·변환 소스 코드 공개", "difficulty": 3,
             "criteria": "담당자가 증빙과 함께 확인한다. 정제·변환 코드가 없거나 공개할 수 없으면 해당 없음으로 기록한다",
             "remedy": "정제·변환에 쓴 코드의 저장소 위치와 라이선스를 증빙으로 남긴다"},
    "R-08": {**ATTEST, "name": "데이터·메타데이터·핵심 문서의 동일 경로 제공", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다",
             "remedy": "데이터, 메타데이터, 스키마·데이터 사전·접근 안내를 한 경로에서 볼 수 있는지 확인하고 그 주소를 증빙으로 남긴다"},
    "R-09": {**ATTEST, "name": "변경 시 메타데이터·문서 동시 현행화", "difficulty": 2,
             "criteria": "담당자가 증빙과 함께 확인한다",
             "remedy": "데이터가 바뀔 때 메타데이터와 문서를 함께 고치는 절차를 확인하고 증빙을 남긴다"},
    "R-10": {**builtin("data_card"), "method": G, "name": "데이터 카드 제공", **meta3("card_background"), "difficulty": 2,
             "criteria": "STEP 7 에서 부록 4 양식의 데이터 카드를 산출했고 필수 칸(해당 시 칸 제외)을 90% 이상 채웠으면 충족, 50% 이상이면 부분, 그 미만이거나 산출하지 않았으면 미흡",
             "remedy": "STEP 3 의 데이터 카드 항목과 데이터 사전을 채운 뒤 STEP 6 검증과 STEP 7 변환을 다시 실행한다"},
    "R-11": {**builtin("pii"), "method": H, "allow_na": True, "name": "재식별 위험 평가와 문서화", "difficulty": 3,
             "criteria": "개인정보 의심 컬럼을 찾지 못하면 해당 없음, 찾으면 담당자가 재식별 위험 평가 결과를 증빙과 함께 확인한다",
             "remedy": "재식별 위험 평가 결과와 조치 사항을 적은 문서의 위치를 증빙으로 남긴다"},
    "R-12": {**builtin("minted"), "method": G, "name": "영구 식별자(PID) 부여", "route": "mint", "difficulty": 1,
             "criteria": "민팅 대장에 발행 ID(DST-000001 형식)가 등록되어 있으면 충족. 초안 ID 만 있으면 미흡",
             "remedy": "STEP 6 에서 관리자가 발행 ID 를 발급한다"},
    "R-13": {**builtin("web_api"), "method": G, "name": "웹 표준 API 제공", **meta3("endpoint_url"), "difficulty": 2,
             "criteria": "http(s) API 엔드포인트(dcat:endpointURL)가 정본 그래프에 있으면 충족. http(s) 가 아닌 엔드포인트(예: 메시지 브로커 주소)만 있으면 부분, 없으면 미흡. 파일형 데이터셋은 배포본의 dcat:accessService 로 적는다",
             "remedy": "API 로 제공하고 있다면 STEP 3 의 API 엔드포인트 URL 에 주소를 입력한다"},
    "R-14": {**builtin("api_alt"), "method": G, "name": "API 외 추가 제공 경로", **meta3("access_url"), "applies": "dataset", "difficulty": 1,
             "criteria": "API 엔드포인트가 선언된 데이터셋에 파일 접속 URL(dcat:accessURL)도 있으면 충족, 없으면 미흡. API 엔드포인트가 없으면 해당 없음",
             "remedy": "STEP 3 의 접속 URL 에 파일을 내려받을 수 있는 주소를 입력한다"},
    "R-15": {**builtin("api_hint"), "method": H, "allow_na": True, "name": "API 응답의 메타데이터 연계", "difficulty": 3,
             "criteria": "API 엔드포인트가 선언되어 있지 않으면 해당 없음. 있으면 담당자가 증빙과 함께 확인한다",
             "remedy": "API 응답에 메타데이터가 들어 있는지, 또는 메타데이터 참조 링크가 있는지 확인하고 증빙을 남긴다"},
    "R-16": {**builtin("api_hint"), "method": H, "allow_na": True, "name": "필터링·분할 조회 기능", "difficulty": 3,
             "criteria": "API 엔드포인트가 선언되어 있지 않으면 해당 없음. 있으면 담당자가 증빙과 함께 확인한다",
             "remedy": "API 가 필터링·조건 검색·페이지네이션을 지원하는지 확인하고 API 문서 위치를 증빙으로 남긴다"},
    "R-17": {**ask("?this owl:versionInfo ?v . ?this adms:versionNotes ?n",
                   "{ ?this owl:versionInfo ?v } UNION { ?this adms:versionNotes ?n } UNION { ?this dcterms:modified ?m }"),
             "method": G, "name": "버전별 변경 이력 제공", **meta3("version_notes"), "difficulty": 1,
             "criteria": "버전(owl:versionInfo)과 버전 노트(adms:versionNotes)가 둘 다 있으면 충족, 버전·버전 노트·수정일시 중 일부만 있으면 부분",
             "remedy": "STEP 3 에서 버전과 버전 노트를 입력한다"},
    "R-18": {**ask("?this dcat:distribution ?d . ?d spdx:checksum ?c . ?c spdx:checksumValue ?v"), "method": G, "name": "전자서명·해시값 제공",
             "route": "mediaType", "applies": "dataset", "difficulty": 1,
             "criteria": "배포본에 해시값(spdx:checksum)이 있으면 충족. 업로드할 때 계산한 SHA-256 을 배포본에 자동으로 적는다. 스트림은 해당 없음",
             "remedy": "STEP 3 에서 데이터셋 유형(미디어타입)을 승인하면 해시값이 배포본에 기록된다"},
    # A6 체크리스트 유형별 (U = 유형별. 규칙 세트 0.x 의 T-01 담당자 확인 기록과 겹치지 않게 접두를 바꿨다)
    "U-01": {**builtin("numeric_hint"), "method": H, "allow_na": True, "name": "수치 데이터의 산출 규칙 제공", "difficulty": 2,
             "criteria": "수치 컬럼이 없으면 해당 없음. 있으면 담당자가 산식·집계 단위·기준시점 제공 여부를 증빙과 함께 확인한다",
             "remedy": "수치 항목의 산식, 집계 단위, 기준시점을 적은 문서의 위치를 증빙으로 남긴다"},
    "U-02": {**builtin("pii"), "method": H, "allow_na": True, "name": "민감 정보 마스킹과 재식별 위험성 평가", "difficulty": 3,
             "criteria": "개인정보 의심 컬럼을 찾지 못하면 해당 없음, 찾으면 담당자가 마스킹·익명화와 재식별 위험성 평가를 증빙과 함께 확인한다",
             "remedy": "의심 컬럼의 마스킹·익명화 처리와 재식별 위험성 평가 결과를 확인하고 증빙을 남긴다"},
    "U-03": {**builtin("pii"), "method": H, "allow_na": True, "name": "비식별 가공 범위와 주의사항 안내", "difficulty": 2,
             "criteria": "개인정보 의심 컬럼을 찾지 못하면 해당 없음, 찾으면 담당자가 가공 범위·원칙·주의사항 안내 여부를 증빙과 함께 확인한다",
             "remedy": "비식별·가공으로 생기는 정보 공백이나 왜곡 가능성을 이용자에게 안내한 위치를 증빙으로 남긴다"},
}

rules = []


def add(rid, area, level, name, text, basis, extra=None):
    sp = dict(spec[rid])
    r = {"id": rid, "area": area, "level": level, "name": sp.pop("name", name), "text": text, "basis": basis}
    r.update(extra or {})
    section_no = sp.pop("section", None)
    if section_no:
        r["basis"] = f"{basis} · {section_no}절"
    r["method"] = sp.pop("method")
    if r["method"] == "AUTO-DERIVED":
        ids = sp["resolver"]["from"]
        sp.setdefault("criteria", f"연결 항목 {len(ids)}개의 판정 점수 평균이 100%면 충족, 50% 이상이면 부분, 그 미만이면 미흡. 연결 항목이 전부 확인 대기면 확인 대기")
        sp.setdefault("remedy", "아래 연결 항목을 조치하면 함께 오른다")
        sp.setdefault("difficulty", 2)
    r.update(sp)
    rules.append(r)


n = 0
for row in t9 + t10 + t11:
    if row["level"] == "필수":
        n += 1
        table = "표 9 데이터 관리 메타데이터" if row in t9 else ("표 10 데이터 계보 메타데이터" if row in t10 else "표 11 데이터 이용 메타데이터")
        add(f"M-{n:02d}", "A1", "필수", row["name"], row["text"], table, {"property": row["property"]})
assert n == 22, n
n = 0
for row in t9 + t12:
    if row["level"] != "필수":
        n += 1
        table = "표 9 데이터 관리 메타데이터" if row in t9 else "표 12 데이터 품질 메타데이터"
        add(f"O-{n:02d}", "A2", row["level"], row["name"], row["text"], table, {"property": row["property"]})
assert n == 7, n
for k in range(1, 16):
    add(f"P-{k:02d}", "A3", "원칙", f"원칙 {k:02d}", principles[k], f"FAIR 원칙 {k:02d}")
for k, row in enumerate(req, start=1):
    add(f"C-{k:02d}", "A4", "필수", "", row["text"], f"부록 3 공통 · {row['group']}", {"group": row["group"]})
for k, row in enumerate(rec, start=1):
    add(f"R-{k:02d}", "A5", "권장", "", row["text"], f"부록 3 공통 · {row['group']}", {"group": row["group"]})
for k, row in enumerate(typed, start=1):
    add(f"U-{k:02d}", "A6", row["level"], "", row["text"], f"부록 3 유형별 · {row['group']}", {"group": row["group"]})

assert len(rules) == 80 and len({r["id"] for r in rules}) == 80
ids = {r["id"] for r in rules}
for r in rules:
    assert r["name"] and r["text"] and r["criteria"] and r["remedy"], r["id"]
    if r["resolver"]["type"] == "derived":
        assert set(r["resolver"]["from"]) <= ids and r["id"] not in r["resolver"]["from"], r["id"]
        # 종합 항목이 종합 항목을 참조할 수는 있지만(P-03 → C-05) 그 아래는 종합 항목이 아니어야 한다 (순환 방지)
        for c in r["resolver"]["from"]:
            child = next(x for x in rules if x["id"] == c)
            if child["resolver"]["type"] == "derived":
                assert all(next(x for x in rules if x["id"] == g)["resolver"]["type"] != "derived" for g in child["resolver"]["from"]), r["id"]

doc = {
    "version": "fde-rules-1.0",
    "guideline": "공공데이터의 인공지능 친화적 관리 가이드라인 v1.1 (행정안전부·NIA, 2026.07)",
    "total_items_in_guideline": 80,
    "note": "가이드라인 v1.1 에서 표 9~11 의 메타데이터 필수 22항목, 표 9·12 의 권장·선택 7항목, 15개 원칙, 부록 3 체크리스트의 공통 필수 15 · 공통 권장 18 · 유형별(수치·개인정보 보호) 3항목을 "
            "원문 문구 그대로 옮긴 80항목이다. 가이드라인 본문에 '80항목'이라는 표현은 없으며, 이 구성은 목업의 영역 구분을 원문에 대조한 것이다. "
            "항목 문구는 원문이고, 판정 기준과 조치 방법은 이 스튜디오가 정한 것이다. "
            "다음은 넣지 않았다: 부록 3 유형별의 이미지/영상 2항목, 표 13~16 의 데이터 타입별 메타데이터(수치 4 · 이미지 4 · 음성 3 · 영상 5). "
            "15개 원칙은 가이드라인에 판정 기준이 없어, 관련된 세부 항목의 판정을 종합하거나(12개) 분류 결과(원칙 12·15) 또는 담당자 확인(원칙 10)으로 판정한다.",
    "scoring": {"met": 1.0, "partial": 0.5, "unmet": 0.0, "pending": 0.0},
    "areas": [
        {"id": "A1", "name": "메타데이터 필수 항목 (표 9~11)", "guideline_items": 22},
        {"id": "A2", "name": "메타데이터 권장·선택 항목 (표 9·12)", "guideline_items": 7},
        {"id": "A3", "name": "15개 원칙", "guideline_items": 15},
        {"id": "A4", "name": "체크리스트 공통 필수 (부록 3)", "guideline_items": 15},
        {"id": "A5", "name": "체크리스트 공통 권장 (부록 3)", "guideline_items": 18},
        {"id": "A6", "name": "체크리스트 유형별 (수치·개인정보)", "guideline_items": 3},
    ],
    "methods": [
        {"id": "AUTO-GRAPH", "name": "정본 그래프 질의와 검증·변환 실행 결과로 자동 판정"},
        {"id": "AUTO-PROFILE", "name": "원천 파일의 프로파일 통계로 자동 판정"},
        {"id": "AUTO-DERIVED", "name": "연결된 세부 항목의 판정을 종합해 자동 판정"},
        {"id": "HUMAN-ATTEST", "name": "담당자가 증빙과 함께 확인 (확인도 prov:Activity 로 기록)"},
    ],
    "rules": rules,
}
for a in doc["areas"]:
    assert len([r for r in rules if r["area"] == a["id"]]) == a["guideline_items"], a
json.dump(doc, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print("rules", len(rules), dict(Counter(r["method"] for r in rules)), dict(Counter(r["area"] for r in rules)))
