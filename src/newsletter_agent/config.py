import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    naver_imap_host: str
    naver_imap_port: int
    naver_imap_user: str
    naver_imap_app_password: str
    anthropic_api_key: str
    claude_model: str
    seen_urls_retention_days: int
    slack_webhook_url: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            naver_imap_host=os.environ.get("NAVER_IMAP_HOST", "imap.naver.com"),
            naver_imap_port=int(os.environ.get("NAVER_IMAP_PORT", "993")),
            naver_imap_user=_require_env("NAVER_IMAP_USER"),
            naver_imap_app_password=_require_env("NAVER_IMAP_APP_PASSWORD"),
            anthropic_api_key=_require_env("ANTHROPIC_API_KEY"),
            claude_model=os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5"),
            seen_urls_retention_days=int(os.environ.get("SEEN_URLS_RETENTION_DAYS", "30")),
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
        )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value
