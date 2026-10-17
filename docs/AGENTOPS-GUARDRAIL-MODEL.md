# 스튜디오 정본을 AgentOps 하네스·가드레일 규칙으로 쓰는 구조 검토

2026-10-17. 질문: "데이터를 가져오고, 거기에 업무를 입히고, 그 업무를 수행하는 팀과 팀원이 데이터셋에 매핑되는" 스튜디오의 구조가 다음 제품(AgentOps)의 하네스·가드레일 기본 규칙이 될 수 있는가. JSON-LD 같은 표준 표현으로 전부 담기고, 그것이 실행 시점의 규칙으로 쓰일 수 있는가.

## 1. 결론

**가능하고, 지금 정본 구조가 이미 그 방향으로 70% 와 있다.** 다만 두 가지를 분명히 해야 한다.

1. **JSON-LD(정본 그래프)는 "규칙의 원천"이지 "규칙 엔진"이 아니다.** 사람·팀·업무·데이터셋·허용 행위·조건·의무는 모두 표준 어휘(DCAT 3 · PROV-O · ORG · ODRL 2.2 · DPV)로 담긴다. 그러나 에이전트가 도구를 부르는 순간 밀리초 안에 판정하려면, 정본에서 **정책 번들을 컴파일**해 하네스가 읽는 구조가 필요하다. 정본 → 번들 변환이 결정적(deterministic)이고 체크섬으로 묶이면 "규칙의 출처가 정본" 이라는 성질은 유지된다.
2. **"팀원 ↔ 데이터셋" 직접 매핑은 피하고 "사람 → 역할(소속) → 정책 → 데이터셋" 으로 간다.** 사람이 바뀌어도 정책이 바뀌지 않고, 정본에 개인 식별 정보를 최소로 담으며(N²SF · 개인정보 보호법), 에이전트에게는 "누구를 대신해 어떤 역할로 행동하는가"(prov:actedOnBehalfOf) 만 넘기면 된다.

## 2. 지금 정본이 이미 담고 있는 것

| 개념 | 표준 표현 | 상태 |
|---|---|---|
| 데이터셋 · 배포본 · 스트림 | dcat:Dataset / dcat:Distribution / dcat:DataService | 있음 |
| 컬럼 구조 | csvw:Column (IRI 가 있어 **컬럼 단위 대상 지정 가능**) | 있음 |
| 등급 | fde:n2sfGrade (SKOS 개념), dcterms:accessRights | 있음, S1/S2 · 근거 예정 |
| 허용 행위 (AI 학습 · 결합 · 자동화 접근 · 대량 호출 · 재배포) | odrl:Set / permission / prohibition / duty (표 39) | 있음 |
| 결합 관계 · 연계키 · SSOT 우선순위 | dcat:qualifiedRelation, fde:JoinKeyBinding, fde:ssotPriority | 있음 |
| 이력 (누가 언제 무엇을) | prov:Activity / prov:wasAssociatedWith / prov:SoftwareAgent | 있음 |
| AI 보조 작성 | fde:AiAssistance + prov:SoftwareAgent (v0.12) | 있음 |
| 에이전트 자격 | AgentKey(등급 · 도구 · 상한 · 유효기간), 호출 기록 | 있음 (DB, 정본 밖) |

## 3. 빠진 것과 채우는 표준

| 빠진 개념 | 쓸 어휘 | 뜻 |
|---|---|---|
| 팀 · 부서 · 역할 · 소속 | **W3C ORG**: org:Organization, org:OrganizationalUnit, org:Role, org:Membership(사람 + 역할 + 조직 + 기간) | "교통안전팀의 데이터 담당 역할" 을 IRI 로 |
| 사람 · 대리 행위 | prov:Person, prov:Agent, **prov:actedOnBehalfOf** | 에이전트가 팀원 A 를 대신해 역할 R 로 행동 |
| 업무 (Task) | 두 겹으로: ① 업무 정의 = `fde:Task` (dcterms:type, 목적, 필요한 데이터셋, 허용 행위, 위험 수준) ② 업무 수행 = prov:Activity (prov:used 데이터셋, prov:wasAssociatedWith 에이전트·사람, prov:qualifiedAssociation 에 역할) | "업무를 입힌다" = Task 정의가 데이터셋을 `fde:requires` 로 가리키고, ODRL 정책이 그 Task 를 **목적(odrl:purpose)** 으로 참조 |
| 목적 · 법적 근거 · 처리 유형 | **DPV** (Data Privacy Vocabulary): dpv:Purpose, dpv:LegalBasis, dpv:Processing (Collect · Combine · Analyse · Share …) | 개인정보 보호법 · AI 기본법 대응 문구를 코드로 |
| 정책의 대상 지정자 | odrl:assignee = org:Role 또는 에이전트 집합(odrl:PartyCollection) | 사람이 아니라 역할에 정책을 건다 |
| 조건 | odrl:constraint: purpose · dateTime · count(일일 상한) · recipient · spatial · **fde:channel**(UI / API / MCP / 배치) · **fde:riskLevel** | 가이드라인 3.6.1 의 "활용 환경" 축 |
| 의무 | odrl:duty: 기록(fde:log), 마스킹(fde:mask 컬럼 목록), 출처 표기(odrl:attribute), 승인(fde:obtainApproval → 검수 큐) | 가드레일의 "허용하되 조건부" |
| 승인 필요 결정 | ODRL 에는 permit / deny 만 있음 → 프로파일 용어 **fde:requiresReview** (permission + duty fde:obtainApproval 로 표현) | HITL (표 40) 을 규칙으로 |
| 충돌 해결 | odrl:conflict = odrl:prohibit (금지 우선) | N²SF "섞이면 최고 등급" 과 같은 원칙 |

## 4. 가드레일 규칙 한 건의 모양

모든 규칙은 다섯 요소로 환원된다: **주체(역할·에이전트) × 행위 × 대상(데이터셋·컬럼) × 맥락(목적·채널·시간·등급·위험) → 결정(permit / deny / review) + 의무(log · mask · attribute · approve)**. ODRL 로 쓰면:

```json
{
  "@context": ["http://www.w3.org/ns/odrl.jsonld", {"fde": "https://catalog.example.go.kr/def/", "org": "http://www.w3.org/ns/org#", "dpv": "https://w3id.org/dpv#"}],
  "@type": "Set", "uid": "fde:policy/traffic-analysis-2026",
  "profile": "fde:odrl-profile", "conflict": "prohibit",
  "permission": [{
    "assignee": {"@id": "fde:role/traffic-safety-analyst", "@type": "org:Role"},
    "action": ["read", "fde:aggregate", "fde:combine"],
    "target": ["fde:id/dataset/DST-000001", "fde:id/dataset/DST-000002"],
    "constraint": [
      {"leftOperand": "purpose", "operator": "isA", "rightOperand": "fde:task/road-accident-cause-analysis"},
      {"leftOperand": "fde:channel", "operator": "isAnyOf", "rightOperand": ["MCP", "UI"]},
      {"leftOperand": "fde:n2sfGrade", "operator": "lteq", "rightOperand": "S1"},
      {"leftOperand": "count", "operator": "lteq", "rightOperand": 500, "unit": "fde:perDay"}
    ],
    "duty": [
      {"action": "fde:log"},
      {"action": "fde:mask", "target": "fde:id/dataset/DST-000002#schema-col-7"},
      {"action": "fde:obtainApproval", "constraint": [{"leftOperand": "fde:riskLevel", "operator": "eq", "rightOperand": "high"}]}
    ]
  }],
  "prohibition": [{
    "assignee": "fde:role/traffic-safety-analyst",
    "action": ["fde:aiTraining", "distribute"],
    "target": "fde:id/dataset/DST-000002"
  }]
}
```

같은 내용이 정본 Turtle 에도 그대로 들어가며(이미 표 39 가 이 방식), 업무 `fde:task/road-accident-cause-analysis` 는 `fde:Task` 로 정의되고 `fde:requires` 로 데이터셋을 가리킨다. 에이전트 호출 한 건의 실제 수행은 prov:Activity 로 남아 "규칙(정책) → 수행(활동)" 이 그래프에서 연결된다.

## 5. 실행 구조 (하네스에서 쓰는 법)

```
정본 그래프 (Turtle/JSON-LD, 체크섬)  ──컴파일──▶  정책 번들 (역할별 · 키별 JSON, 번들 체크섬 = 정본 체크섬 묶음)
                                                        │
AgentOps 하네스:  도구 호출 전  ── PDP 판정 ◀──────────┘   (주체·행위·대상·맥락 → permit/deny/review + 의무)
                  도구 호출 후  ── 출력 가드 (의무 집행: 마스킹 · 샘플 제거 · 출처 표기 · 기록)
                  세션 전체    ── 상한 · 이력 · 이상 징후 (count 제약, 거부 누적)
                                                        │
                  판정 · 집행 결과 ──▶ prov:Activity 로 스튜디오에 회신 (규칙 ↔ 수행 연결)
```

- **정책 결정점(PDP)**: 1차는 스튜디오 안의 경량 평가기(지금 MCP 의 `visible()` · 키 등급 · 일일 상한이 그 원형)로 충분하다. 규모가 커지면 번들을 OPA(Rego) 나 Cedar 로 내보낸다. ODRL → Rego 변환은 제약 연산자가 유한해서 기계적으로 된다.
- **번들에는 사람 이름이 들어가지 않는다.** 역할 IRI 와 에이전트 키 ID 만. 사람 ↔ 역할은 스튜디오(ORG 소속)에서만 풀고, 하네스에는 "이 세션은 역할 R, 대리 대상 사용자 ID u" 만 전달한다.
- **컬럼 단위 의무**(마스킹 · 제외)는 csvw:Column IRI 를 target 으로 쓰면 되므로, 컬럼 등급을 도입하기 전이라도 "이 컬럼은 외부로 내보내지 않는다" 류 규칙은 지금 표현할 수 있다.
- **검증**: 정책 번들에 대해 STEP 8 과 같은 식의 자동 테스트(이 주체가 이 행위를 하면 deny 여야 한다)를 두고, 정본 변경 → 번들 재컴파일 → 테스트 → 배포 순서를 CI 로 묶는다. 규칙의 변경 이력도 prov:Activity 로 남긴다.

## 6. JSON-LD 만으로 안 되는 것 (정직하게)

| 한계 | 대응 |
|---|---|
| 실행 시점 상태(오늘 몇 번 불렀나, 지금 위험 수준) 는 그래프에 없다 | 하네스가 상태를 들고 제약(count · riskLevel)을 평가. 그래프는 **임계값**만 정한다 |
| 모델 출력 내용 검사(생성 텍스트에 개인정보가 섞였는가)는 규칙으로 못 쓴다 | 출력 가드는 별도 분류기 · 패턴 검사. 규칙은 "검사를 반드시 거친다"(duty) 까지만 |
| 그래프 질의(SPARQL)는 호출마다 돌리기엔 느리다 | 컴파일된 번들로 판정. SPARQL/SHACL 은 번들 생성 · 검증 시점에만 |
| ODRL 에 "승인 필요" 결정이 없다 | 프로파일 용어 fde:obtainApproval duty 로 표현, 하네스가 review 로 해석 |
| 업무(Task) 의미를 표준이 정의하지 않는다 | fde:Task 를 두되 DPV purpose · PROV plan(prov:Plan) 과 연결해 외부 도구도 읽게 |
| 조합(여러 데이터셋 동시 사용) 위험은 개별 정책의 합이 아니다 | 조합 단위 정책(target 이 조합 데이터셋)과 결합 금지 제약(fde:combineWith notIn …) 을 따로 둔다 |

## 7. 스튜디오에 먼저 넣을 것 (AgentOps 전 단계)

1. **역할 · 소속 모델**: 기관 › 부서 › 역할, 사용자 ↔ 소속(기간). 지금의 admin/worker/viewer 는 시스템 권한이고, 업무 역할은 별도 축. ORG 로 정본에 내보낸다.
2. **업무(Task) 등록**: 프로세스(조합)에 "이 조합이 지원하는 업무" 를 1개 이상 등록. 업무 = 이름 · 목적(DPV) · 책임 역할 · 위험 수준 · 허용 행위 기본값. 정본에 fde:Task + prov:Plan.
3. **정책 편집기 (표 39 확장)**: 데이터셋 단위 5항목을 "역할 × 행위 × 조건 × 의무" 로 넓힌 화면. 기본값은 등급(N²SF 기획안 4절)에서 자동 생성.
4. **정책 번들 내보내기**: `GET /api/policy-bundle?role=…` 가 ODRL JSON-LD 와 평가용 평탄 JSON 을 함께 준다. MCP 키는 번들을 참조한다.
5. **수행 회신 API**: 하네스가 판정·집행 결과를 prov:Activity 로 올리는 엔드포인트. 이것이 있어야 "규칙 → 수행" 이 한 그래프에 남고, 가이드라인 표 40 이력 관리와 AI 기본법 제34조 문서 보관이 자동으로 된다.

이 다섯이 있으면 AgentOps 는 새 규칙 언어를 만들 필요 없이 스튜디오 번들을 읽는 하네스로 시작할 수 있다.
