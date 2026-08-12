from unittest.mock import patch

import httpx
import pytest
import respx

from newsletter_agent.config import Settings
from newsletter_agent.pipeline import _deliver


def _make_settings(webhook_url: str | None) -> Settings:
    return Settings(
        naver_imap_host="imap.naver.com",
        naver_imap_port=993,
        naver_imap_user="user@naver.com",
        naver_imap_app_password="pw",
        anthropic_api_key="key",
        claude_model="claude-haiku-4-5",
        seen_urls_retention_days=30,
        slack_webhook_url=webhook_url,
    )


@pytest.fixture(autouse=True)
def _no_real_sleep():
    with patch("time.sleep", return_value=None):
        yield


_SAMPLE_BLOCKS = [{"type": "section", "text": {"type": "mrkdwn", "text": "리포트"}}]


@respx.mock
def test_deliver_slack_final_failure_exits_nonzero():
    respx.post("https://hooks.slack.com/services/test").mock(return_value=httpx.Response(500))
    settings = _make_settings("https://hooks.slack.com/services/test")

    with pytest.raises(SystemExit) as exc_info:
        _deliver("리포트", _SAMPLE_BLOCKS, settings, "slack")

    assert exc_info.value.code == 1


@respx.mock
def test_deliver_slack_success_does_not_exit():
    respx.post("https://hooks.slack.com/services/test").mock(return_value=httpx.Response(200))
    settings = _make_settings("https://hooks.slack.com/services/test")

    _deliver("리포트", _SAMPLE_BLOCKS, settings, "slack")  # 예외/exit 없이 정상 종료되어야 함


def test_deliver_console_mode_never_touches_slack():
    settings = _make_settings(None)

    _deliver("리포트", _SAMPLE_BLOCKS, settings, "console")  # Slack 웹훅 미설정이어도 콘솔은 항상 동작
