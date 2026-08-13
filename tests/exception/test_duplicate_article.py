from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from newsletter_agent.dedup.same_day import merge_same_day
from newsletter_agent.dedup.seen_store import SeenStore
from newsletter_agent.models import EmailMessage, Newsletter, NewsletterId
from newsletter_agent.pipeline import _collect_all_articles

FIXTURES = Path(__file__).parent.parent / "fixtures" / "emails"


class _FakeClaudeClient:
    def summarize_text(self, text: str, sentence_range=(3, 5)) -> str:
        return '{"summary": "동일 기사 요약입니다.", "topic": "AI"}'


def _make_newsletter(
    from_addr: str, display_name: str, newsletter_name: str, fixture: str, subject: str
) -> Newsletter:
    html = FIXTURES.joinpath(fixture).read_text(encoding="utf-8")
    email = EmailMessage(
        msg_id=f"{from_addr}-{subject}",
        from_addr=from_addr,
        from_display_name=display_name,
        subject=subject,
        received_at=datetime(2026, 7, 19, 12, 0, 0, tzinfo=UTC),
        html_body=html,
    )
    return Newsletter(newsletter_id=NewsletterId(name=newsletter_name), email=email)


@respx.mock
def test_same_article_in_two_newsletters_merges_with_two_sources(tmp_path):
    respx.head(url__regex=r"https://example\.com/shared.*").mock(return_value=httpx.Response(200))
    respx.get(url__regex=r"https://example\.com/shared.*").mock(
        return_value=httpx.Response(
            200, text="<html><body><article><p>공유된 기사 본문입니다.</p></article></body></html>"
        )
    )

    tldr_html = '<html><body><p><a href="https://example.com/shared?utm_source=tldr">기사</a></p></body></html>'
    geeknews_html = '<html><body><p><a href="https://example.com/shared?utm_source=geeknews">기사</a></p></body></html>'

    tldr_email = EmailMessage(
        msg_id="1", from_addr="dan@tldrnewsletter.com", from_display_name="TLDR AI",
        subject="TLDR Digest", received_at=datetime(2026, 7, 19, 9, 0, 0, tzinfo=UTC), html_body=tldr_html,
    )
    geeknews_email = EmailMessage(
        msg_id="2", from_addr="news@hada.io", from_display_name="", subject="GeekNews Digest",
        received_at=datetime(2026, 7, 19, 10, 0, 0, tzinfo=UTC), html_body=geeknews_html,
    )
    newsletters = [
        Newsletter(newsletter_id=NewsletterId(name="TLDR AI"), email=tldr_email),
        Newsletter(newsletter_id=NewsletterId(name="GeekNews Weekly"), email=geeknews_email),
    ]

    claude_client = _FakeClaudeClient()
    with httpx.Client() as http_client:
        all_articles, _ = _collect_all_articles(newsletters, claude_client, http_client)

    merged = merge_same_day(all_articles)

    assert len(merged) == 1
    source_names = {nl.name for nl in merged[0].source_newsletters}
    assert source_names == {"TLDR AI", "GeekNews Weekly"}

    seen_store = SeenStore.load(tmp_path / "seen_urls.json")
    new_articles = seen_store.filter_new(merged)
    assert len(new_articles) == 1


@respx.mock
def test_article_seen_yesterday_excluded_from_todays_report(tmp_path):
    respx.head(url__regex=r"https://example\.com/shared.*").mock(return_value=httpx.Response(200))
    respx.get(url__regex=r"https://example\.com/shared.*").mock(
        return_value=httpx.Response(
            200, text="<html><body><article><p>공유된 기사 본문입니다.</p></article></body></html>"
        )
    )

    tldr_html = '<html><body><p><a href="https://example.com/shared?utm_source=tldr">기사</a></p></body></html>'
    tldr_email = EmailMessage(
        msg_id="1", from_addr="dan@tldrnewsletter.com", from_display_name="TLDR AI",
        subject="TLDR Digest", received_at=datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC), html_body=tldr_html,
    )
    newsletter = Newsletter(newsletter_id=NewsletterId(name="TLDR AI"), email=tldr_email)

    claude_client = _FakeClaudeClient()
    with httpx.Client() as http_client:
        all_articles, _ = _collect_all_articles([newsletter], claude_client, http_client)

    merged = merge_same_day(all_articles)
    normalized_url = merged[0].normalized_url

    seen_path = tmp_path / "seen_urls.json"
    seen_store = SeenStore({normalized_url: "2026-07-19"})
    seen_store.save(seen_path)

    reloaded_store = SeenStore.load(seen_path)
    new_articles = reloaded_store.filter_new(merged)

    assert new_articles == []
