from newsletter_agent.dedup.same_day import merge_same_day
from newsletter_agent.models import Article, ArticleSummary, NewsletterId
from newsletter_agent.parsing.article_fetch import FetchResult
from newsletter_agent.parsing.links import normalize_url


def _make_article(url: str, newsletter_name: str, status: str = "ok") -> Article:
    return Article(
        url=url,
        normalized_url=normalize_url(url),
        title="제목",
        excerpt="발췌문",
        fetch_result=FetchResult(status=status, text="본문" if status == "ok" else None, reason=status),
        summary=ArticleSummary(text=f"{newsletter_name} 요약", topic="AI"),
        source_newsletters=[NewsletterId(name=newsletter_name)],
    )


def test_same_url_different_tracking_params_merges_with_both_sources():
    article_a = _make_article(
        "https://example.com/post?utm_source=tldr", "TLDR AI"
    )
    article_b = _make_article(
        "https://example.com/post?utm_source=geeknews", "GeekNews Weekly"
    )

    merged = merge_same_day([article_a, article_b])

    assert len(merged) == 1
    source_names = {nl.name for nl in merged[0].source_newsletters}
    assert source_names == {"TLDR AI", "GeekNews Weekly"}


def test_distinct_urls_remain_separate():
    article_a = _make_article("https://example.com/post-a", "TLDR AI")
    article_b = _make_article("https://example.com/post-b", "TLDR IT")

    merged = merge_same_day([article_a, article_b])

    assert len(merged) == 2


def test_merge_prefers_successful_fetch_over_failed():
    failed = _make_article("https://example.com/dup", "TLDR AI", status="not_found")
    succeeded = _make_article("https://example.com/dup?utm_source=x", "GeekNews Weekly", status="ok")

    merged = merge_same_day([failed, succeeded])

    assert len(merged) == 1
    assert merged[0].fetch_result.status == "ok"
    source_names = {nl.name for nl in merged[0].source_newsletters}
    assert source_names == {"TLDR AI", "GeekNews Weekly"}
