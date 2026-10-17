"""애플리케이션 설정. 모든 값은 환경변수(FDE_ 접두)로 덮어쓸 수 있다."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDE_", env_file=".env", extra="ignore")

    # --- 저장소 ---
    database_url: str = "sqlite:///./fde.db"
    storage_dir: Path = Path("./storage")

    # --- 인증 ---
    # 운영 환경에서는 반드시 FDE_SECRET_KEY 를 지정한다 (미지정 시 기동마다 무작위 생성 → 재기동 시 로그인 만료).
    secret_key: str = ""
    token_minutes: int = 60 * 12
    admin_username: str = "admin"
    # 최초 기동 시 관리자 계정을 만들 때만 쓰인다. 비어 있으면 무작위 비밀번호를 만들어 로그에 1회 출력한다.
    admin_password: str = ""
    admin_name: str = "관리자"

    # --- RDF 식별자 ---
    # 발행 IRI의 기준 주소. 기관 도메인에 맞춰 바꾼다.
    base_iri: str = "https://catalog.molit.go.kr"

    # --- 업로드 ---
    max_upload_mb: int = 50
    profile_max_rows: int = 50_000

    # --- AI 초안 제안 (Claude API) ---
    # 비어 있으면 AI 초안 기능이 꺼진다. 메타데이터 서술형 칸의 초안을 만들 때만 쓰며, 개인정보 의심 컬럼의 값은 보내지 않는다.
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"
    ai_max_tokens: int = 4000
    ai_timeout_seconds: int = 90
    # 사용자 한 명이 외부 모델을 부를 수 있는 횟수 (초안 제안 + 시뮬레이션 합산). 0 이면 제한 없음.
    ai_rate_per_minute: int = 6
    ai_rate_per_day: int = 200
    # AI 초안을 채택한 칸을 데이터 카드·카탈로그에 "AI 보조 작성"으로 표시할지 (정본 그래프의 이력은 항상 남는다)
    ai_assist_notice: bool = True

    # --- 발행 검수 ---
    # note: 요청자 본인이 승인할 수 있되 사유 10자 이상 + '자기 승인' 기록 (기본). deny: 본인 승인 금지.
    review_self_approve: str = "note"

    # --- 시간대 --- 하루 호출 상한 · 일일 집계의 '하루' 기준
    timezone: str = "Asia/Seoul"

    # --- 기타 ---
    cors_origins: str = ""
    seed_demo_orgs: bool = True

    @property
    def def_ns(self) -> str:
        return self.base_iri.rstrip("/") + "/def/"

    @property
    def id_ns(self) -> str:
        return self.base_iri.rstrip("/") + "/id/"

    @property
    def shapes_ns(self) -> str:
        return self.base_iri.rstrip("/") + "/shapes/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
