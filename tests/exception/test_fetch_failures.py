from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from newsletter_agent.models import EmailMessage, Newsletter, NewsletterId
from newsletter_agent.pipeline import _process_newsletter_articles

FIXTURES = Path(__file__).parent.parent / "fixtures" / "emails"


class _FakeClaudeClient:
    def summarize_text(self, text: str, sentence_range=(3, 5)) -> str:
        return '{"summary": "요약된 내용입니다.", "topic": "기타"}'


def _make_newsletter() -> Newsletter:
    html = FIXTURES.joinpath("two_links_body.html").read_text(encoding="utf-8")
    email = EmailMessage(
        msg_id="msg-1",
        from_addr="dan@tldrnewsletter.com",
        from_display_name="TLDR IT",
        subject="Two Links Digest",
        received_at=datetime(2026, 7, 19, 12, 0, 0, tzinfo=UTC),
        html_body=html,
    )
    return Newsletter(newsletter_id=NewsletterId(name="TLDR IT"), email=email)


@respx.mock
def test_fetch_failures_produce_distinct_report_annotations():
    respx.head("https://example.com/not-found").mock(return_value=httpx.Response(200))
    respx.head("https://example.com/blocked").mock(return_value=httpx.Response(200))
    respx.get("https://example.com/not-found").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/blocked").mock(return_value=httpx.Response(403))

    newsletter = _make_newsletter()
    claude_client = _FakeClaudeClient()

    with httpx.Client() as http_client:
        articles, cap_applied = _process_newsletter_articles(
            newsletter, claude_client, http_client
        )

    assert cap_applied is False
    assert len(articles) == 2

    not_found_article = next(a for a in articles if a.url.endswith("not-found"))
    blocked_article = next(a for a in articles if a.url.endswith("blocked"))

    assert "원문 확인 불가" in not_found_article.summary.text
    assert "접근 차단됨" in blocked_article.summary.text
    # 두 경우 모두 발췌 기반 요약이 생성되어 있어야 한다 (빈 요약 아님).
    assert not_found_article.summary.text.strip()
    assert blocked_article.summary.text.strip()
