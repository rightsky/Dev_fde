# API 엔드포인트 목록 (자동 생성)

| 메서드 | 경로 | 요청 본문 | 설명 |
|---|---|---|---|
| GET | `/api/activities` | ?process_id&limit | List Activities |
| GET | `/api/artifacts/{aid}` | ?download | Get Artifact |
| GET | `/api/assets` | ?kind&q | List Assets |
| POST | `/api/assets/streams` | StreamIn {name, description?, org_id?, temporal_resolution?, event_time_column?, endpoint_url?, timezone?, fields?} | Register Stream |
| POST | `/api/assets/upload` | multipart files[] | Upload Assets |
| GET | `/api/assets/{asset_id}` |  | Get Asset |
| PATCH | `/api/assets/{asset_id}` | AssetPatch {name?, description?, org_id?} | Update Asset |
| DELETE | `/api/assets/{asset_id}` |  | Delete Asset |
| POST | `/api/auth/login` | LoginIn {username, password} | Login |
| GET | `/api/auth/me` |  | Me |
| POST | `/api/auth/password` | PasswordIn {current_password, new_password} | Change Password |
| GET | `/api/catalog` | ?q&kind&theme&data_type&status | List Catalog |
| GET | `/api/catalog/{resource_id}` |  | Get Entry |
| GET | `/api/catalog/{resource_id}/raw` | ?format | Raw Entry |
| POST | `/api/catalog/{resource_id}/restore` |  | Restore |
| POST | `/api/catalog/{resource_id}/withdraw` |  | 발행 철회. 항목은 삭제하지 않고 상태만 바꾼다 (리니지 추적성 유지). |
| GET | `/api/dashboard` |  | Dashboard |
| GET | `/api/datasets/{did}` |  | Get Dataset |
| PUT | `/api/datasets/{did}/classification` | ClassificationIn {F1?, F2?, F3?, F4?, F5?, F6?, K?, N2SF?} | Put Classification |
| POST | `/api/datasets/{did}/classification/confirm` |  | Confirm Classification |
| GET | `/api/datasets/{did}/classification/suggestions` |  | Classification Suggestions |
| POST | `/api/datasets/{did}/classification/unconfirm` |  | Unconfirm Classification |
| PATCH | `/api/datasets/{did}/meta` | MetaIn {values?, approve?, unapprove?, extra_classes?} | Patch Meta |
| POST | `/api/datasets/{did}/meta/confirm` |  | Confirm Meta |
| POST | `/api/datasets/{did}/meta/unconfirm` |  | Unconfirm Meta |
| GET | `/api/datasets/{did}/preview` |  | 정본 미리보기 + 즉시 검증. STEP 6 과 같은 엔진을 쓰되 실행 기록은 남기지 않는다. |
| GET | `/api/diagnosis-runs/{run_id}/report` |  | 진단 보고서 (인쇄용 HTML — 브라우저 인쇄로 PDF 저장). |
| GET | `/api/health` |  | Health |
| GET | `/api/mint-registry` |  | Mint Registry |
| GET | `/api/orgs` |  | List Orgs |
| POST | `/api/orgs` | OrgIn {code?, label, note?, active?} | Create Org |
| PATCH | `/api/orgs/{org_id}` | OrgIn {code?, label, note?, active?} | Update Org |
| GET | `/api/processes` | ?status | List Processes |
| POST | `/api/processes` | ProcessIn {name?} | Create Process |
| GET | `/api/processes/{pid}` |  | Get Process |
| PATCH | `/api/processes/{pid}` | ProcessPatch {name?, current_step?, pub_mode?} | Update Process |
| DELETE | `/api/processes/{pid}` |  | Purge Process |
| GET | `/api/processes/{pid}/activities` | ?limit | Process Activities |
| PUT | `/api/processes/{pid}/attestations/{item_id}` | AttestIn {status: met·partial·unmet·na, note?, evidence?} | 담당자 확인 기록 (HUMAN-ATTEST 항목만. 미흡 외에는 evidence 필수) |
| PUT | `/api/processes/{pid}/combo` | ComboIn {dataset_ids, source?} | Set Combo |
| POST | `/api/processes/{pid}/combo/confirm` | ComboConfirmIn {title, description?} | Confirm Combo |
| POST | `/api/processes/{pid}/combo/unconfirm` |  | Unconfirm Combo |
| GET | `/api/processes/{pid}/combo/warnings` |  | Combo Warnings |
| POST | `/api/processes/{pid}/complete` |  | Complete Process |
| POST | `/api/processes/{pid}/diagnosis-runs` |  | Run Diagnosis |
| GET | `/api/processes/{pid}/diagnosis-runs/latest` |  | Latest Diagnosis |
| GET | `/api/processes/{pid}/graph` | ?level | Process Graph |
| POST | `/api/processes/{pid}/lineage-waiver` | WaiverIn {reason} | Set Waiver |
| DELETE | `/api/processes/{pid}/lineage-waiver` |  | Clear Waiver |
| POST | `/api/processes/{pid}/mint` |  | Mint |
| POST | `/api/processes/{pid}/publish` |  | Publish |
| GET | `/api/processes/{pid}/relations` |  | List Relations |
| POST | `/api/processes/{pid}/relations` | RelationIn {type, source_id, target_id, key_code?, source_table?, source_column?, target_table?, target_column?, note?, confirm?} | Create Relation |
| PUT | `/api/processes/{pid}/relations/order` | OrderIn {relation_ids} | JOINED_ON 의 SSOT 우선순위 재정렬 (맨 위 = 판단 기준 1순위). |
| POST | `/api/processes/{pid}/reopen` |  | Reopen Process |
| POST | `/api/processes/{pid}/restore` |  | Restore Process |
| PUT | `/api/processes/{pid}/selection` | SelectionIn {asset_ids} | Set Selection |
| POST | `/api/processes/{pid}/serialization-runs` | SerializeIn {formats?} | Run Serialization |
| GET | `/api/processes/{pid}/serialization-runs/latest` |  | Latest Serialization |
| GET | `/api/processes/{pid}/suggestions` |  | Combo Suggestions |
| POST | `/api/processes/{pid}/trash` |  | Trash Process |
| POST | `/api/processes/{pid}/validation-runs` |  | Run Validation |
| GET | `/api/processes/{pid}/validation-runs/latest` |  | Latest Validation |
| GET | `/api/reference` |  | Reference |
| PATCH | `/api/relations/{rid}` | RelationPatch {key_code?, source_table?, source_column?, target_table?, target_column?, note?, priority?} | Update Relation |
| DELETE | `/api/relations/{rid}` |  | Delete Relation |
| POST | `/api/relations/{rid}/confirm` |  | Confirm Relation |
| POST | `/api/relations/{rid}/unconfirm` |  | Unconfirm Relation |
| GET | `/api/serialization-runs/{run_id}/download` |  | Download Zip |
| GET | `/api/shapes` | ?mode | Shapes |
| GET | `/api/taxonomy` |  | Taxonomy |
| PATCH | `/api/taxonomy/codes/{code_id}` | CodeIn {label, definition?, active?} | Update Code |
| POST | `/api/taxonomy/{axis_code}/codes` | CodeIn {label, definition?, active?} | Add Code |
| GET | `/api/users` |  | List Users |
| POST | `/api/users` | UserIn {username, name, password, role?, org_label?, email?} | Create User |
| PATCH | `/api/users/{user_id}` | UserPatch {name?, role?, org_label?, email?, active?, password?} | Update User |
| GET | `/api/validation-runs/{run_id}/report` | ?dataset_id | Validation Report |
