import logging

from newsletter_agent.dedup.same_day import merge_same_day
from newsletter_agent.models import Article, ArticleSummary, NewsletterId
from newsletter_agent.parsing.article_fetch import FetchResult
from newsletter_agent.parsing.links import normalize_url
from newsletter_agent.summarize.report_synthesis import compose_markdown_report, group_by_topic

FAKE_SECRETS = ["sk-ant-supersecretkey123", "naver-app-password-xyz", "T00/B00/fakewebhooksecret"]


def _make_article() -> Article:
    url = "https://example.com/article"
    return Article(
        url=url,
        normalized_url=normalize_url(url),
        title="제목",
        excerpt="발췌",
        fetch_result=FetchResult(status="ok", text="본문", reason="ok"),
        summary=ArticleSummary(text="정상 요약입니다.", topic="AI"),
        source_newsletters=[NewsletterId(name="TLDR AI")],
    )


def test_composed_report_never_contains_secret_values():
    articles = merge_same_day([_make_article()])
    grouped = group_by_topic(articles)
    report = compose_markdown_report("전체 요약입니다.", grouped, [], [])

    for secret in FAKE_SECRETS:
        assert secret not in report


def test_log_output_never_contains_secret_values(caplog):
    caplog.set_level(logging.DEBUG)

    from newsletter_agent.mail.whitelist import Whitelist

    whitelist = Whitelist({"news@hada.io": []})
    whitelist.classify("news@hada.io", "Anything")
    whitelist.classify("unknown@example.com", "Unknown")

    log_text = caplog.text
    for secret in FAKE_SECRETS:
        assert secret not in log_text
