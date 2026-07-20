import json
from datetime import datetime
from pathlib import Path

import httpx
import respx

from newsletter_agent.dedup.same_day import merge_same_day
from newsletter_agent.dedup.seen_store import SeenStore
from newsletter_agent.delivery.slack import send_to_slack
from newsletter_agent.mail.whitelist import Whitelist
from newsletter_agent.models import EmailMessage
from newsletter_agent.pipeline import _classify_all, _collect_all_articles, _compose_final_report

WHITELIST_PATH = Path(__file__).parent.parent.parent / "whitelist.yaml"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "emails"


class _FakeClaudeClient:
    """기사 본문/발췌문에 따라 그럴듯한 JSON 요약을 돌려주는 가짜 Claude 클라이언트."""

    def summarize_text(self, text: str, sentence_range=(3, 5)) -> str:
        # 전체 요약 합성 호출은 여러 기사 요약을 컨텍스트로 받으므로 대괄호 토픽 라벨(예: "[AI]")이 다수 포함된다.
        if text.count("[AI]") + text.count("[개발]") + text.count("[스타트업]") >= 2:
            return "오늘은 AI, 개발, 스타트업 소식이 있었습니다.\n각 분야에서 주목할 만한 발표가 있었습니다.\n전반적으로 활발한 한 주였습니다."
        if "AI 기사 본문" in text:
            return '{"summary": "AI 기사 요약입니다.", "topic": "AI"}'
        if "개발 기사 본문" in text:
            return '{"summary": "개발 기사 요약입니다.", "topic": "개발"}'
        if "스타트업 기사 본문" in text:
            return '{"summary": "스타트업 기사 요약입니다.", "topic": "스타트업"}'
        raise AssertionError(f"Unexpected prompt in fake Claude client: {text!r}")


def _make_email(from_addr: str, display_name: str, subject: str, fixture_name: str) -> EmailMessage:
    html = FIXTURES.joinpath(fixture_name).read_text(encoding="utf-8")
    return EmailMessage(
        msg_id=f"{from_addr}-{display_name}-{subject}",
        from_addr=from_addr,
        from_display_name=display_name,
        subject=subject,
        received_at=datetime(2026, 7, 20, 9, 0, 0),
        html_body=html,
    )


@respx.mock
def test_three_fixture_newsletters_produce_expected_report_and_slack_delivery():
    # 리다이렉트 해석(HEAD)과 기사 fetch(GET) 모킹
    for path, article_html in [
        ("ai-article", "<html><body><article><p>AI 기사 본문입니다.</p></article></body></html>"),
        ("dev-article", "<html><body><article><p>개발 기사 본문입니다.</p></article></body></html>"),
        ("startup-news", "<html><body><article><p>스타트업 기사 본문입니다.</p></article></body></html>"),
    ]:
        url = f"https://example.com/{path}"
        respx.head(url).mock(return_value=httpx.Response(200))
        respx.get(url).mock(return_value=httpx.Response(200, text=article_html))

    whitelist = Whitelist.load(WHITELIST_PATH)
    emails = [
        _make_email("dan@tldrnewsletter.com", "TLDR AI", "AI Digest", "tldr_integration_body.html"),
        _make_email("news@hada.io", "", "GeekNews Digest", "geeknews_integration_body.html"),
        _make_email(
            "newsletter@mail.routinecrew.net", "Newsletter", "Routinecrew Digest", "routinecrew_body.html"
        ),
    ]

    newsletters = _classify_all(whitelist, emails)
    assert {nl.newsletter_id.name for nl in newsletters} == {
        "TLDR AI",
        "GeekNews Weekly",
        "Newsletter",
    }

    claude_client = _FakeClaudeClient()
    with httpx.Client() as http_client:
        all_articles, cap_applied = _collect_all_articles(newsletters, claude_client, http_client)

    assert len(all_articles) == 3
    assert not any(cap_applied.values())

    merged = merge_same_day(all_articles)
    seen_store = SeenStore({})
    new_articles = seen_store.filter_new(merged)

    report = _compose_final_report(new_articles, claude_client, cap_applied, [])

    # 구조 검증: 전체요약 섹션, 주제 그룹, 기사별 링크+요약 모두 존재
    assert "## 오늘의 핵심 요약" in report
    assert "## AI" in report
    assert "## 개발" in report
    assert "## 스타트업" in report
    assert "[AI 기사 읽기](https://example.com/ai-article)" in report
    assert "[개발 기사 읽기](https://example.com/dev-article)" in report
    assert "[스타트업 뉴스 읽기](https://example.com/startup-news)" in report
    assert "(TLDR AI)" in report
    assert "(GeekNews Weekly)" in report
    assert "(Newsletter)" in report

    # Slack 전송 확인
    slack_route = respx.post("https://hooks.slack.com/services/test").mock(
        return_value=httpx.Response(200)
    )
    send_to_slack("https://hooks.slack.com/services/test", report)

    assert slack_route.call_count == 1
    sent_body = json.loads(respx.calls.last.request.content)
    assert sent_body["text"] == report
